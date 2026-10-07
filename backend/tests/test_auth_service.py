"""Unit tests for app.services.auth_service: token issuance, single-use
consumption, resend/invalidation, expiry and purpose-scoping, and the
verification/reset emails it sends.

app/tests/test_auth.py already exercises this module end-to-end through the
/auth routes; these tests instead call auth_service's functions directly
against a real session, the way app/routers/auth.py does, so a regression
in the service itself fails here even if a router kept working around it.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.database import Base, engine
from app.database import SessionLocal as _SessionLocal
from app.models import AuthToken, User
from app.security import hash_password
from app.services import auth_service, mailer


@pytest.fixture(autouse=True)
def _clean_state():
    mailer.OUTBOX.clear()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


def _make_user(email="user@example.com", password="Password1", is_verified=True) -> User:
    with _SessionLocal() as db:
        user = User(email=email, password_hash=hash_password(password), is_verified=is_verified)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


# ------------------------------------------------------------- issuance ---


def test_issue_verification_token_creates_a_hashed_single_use_row():
    user = _make_user()

    with _SessionLocal() as db:
        raw_token = auth_service.issue_verification_token(db, user)

    with _SessionLocal() as db:
        rows = db.query(AuthToken).filter(AuthToken.user_id == user.id).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.purpose == "verify"
        assert row.used_at is None
        # The raw token is never stored as-is -- only its hash -- so a reader
        # of the token table (or a DB backup) can't recover a usable
        # credential.
        assert row.token_hash != raw_token
        assert row.token_hash == auth_service._hash_token(raw_token)


def test_issue_verification_token_sets_roughly_a_24h_expiry():
    user = _make_user()
    before = datetime.now(UTC)

    with _SessionLocal() as db:
        auth_service.issue_verification_token(db, user)

    with _SessionLocal() as db:
        row = db.query(AuthToken).filter(AuthToken.user_id == user.id).one()
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        delta = expires_at - before
        assert timedelta(hours=23, minutes=59) < delta <= timedelta(hours=24, minutes=1)


def test_issue_password_reset_token_sets_roughly_a_1h_expiry():
    user = _make_user()
    before = datetime.now(UTC)

    with _SessionLocal() as db:
        auth_service.issue_password_reset_token(db, user)

    with _SessionLocal() as db:
        row = (
            db.query(AuthToken)
            .filter(AuthToken.user_id == user.id, AuthToken.purpose == "password_reset")
            .one()
        )
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        delta = expires_at - before
        assert timedelta(minutes=59) < delta <= timedelta(hours=1, minutes=1)


def test_reissuing_a_verification_token_invalidates_the_earlier_one():
    """The resend path (AC-004): calling issue again must not leave two
    valid tokens able to verify the same account."""
    user = _make_user()
    with _SessionLocal() as db:
        first_token = auth_service.issue_verification_token(db, user)
    with _SessionLocal() as db:
        second_token = auth_service.issue_verification_token(db, user)

    assert second_token != first_token

    with _SessionLocal() as db:
        with pytest.raises(auth_service.TokenError):
            auth_service.consume_token(db, first_token, "verify")

    # The replacement remains usable.
    with _SessionLocal() as db:
        verified_user = auth_service.consume_token(db, second_token, "verify")
        assert verified_user.id == user.id


def test_reissuing_repeatedly_invalidates_every_earlier_unused_token():
    """A resend can happen more than once (double-click, slow network, a
    second "resend" click before the first email even arrives). Every
    still-unused token issued before the latest one must be invalidated --
    not just the single immediately-preceding one -- or a stale link mailed
    earlier in the sequence would stay able to verify the account."""
    user = _make_user()
    with _SessionLocal() as db:
        first_token = auth_service.issue_verification_token(db, user)
    with _SessionLocal() as db:
        second_token = auth_service.issue_verification_token(db, user)
    with _SessionLocal() as db:
        third_token = auth_service.issue_verification_token(db, user)

    with _SessionLocal() as db:
        with pytest.raises(auth_service.TokenError):
            auth_service.consume_token(db, first_token, "verify")
    with _SessionLocal() as db:
        with pytest.raises(auth_service.TokenError):
            auth_service.consume_token(db, second_token, "verify")
    with _SessionLocal() as db:
        verified_user = auth_service.consume_token(db, third_token, "verify")
        assert verified_user.id == user.id


def test_reissuing_does_not_touch_an_already_used_token():
    """Invalidation is scoped to unused tokens; a token already consumed
    keeps the `used_at` its consumption set, rather than having a later
    reissue stamp over it."""
    user = _make_user()
    with _SessionLocal() as db:
        first_token = auth_service.issue_verification_token(db, user)
    with _SessionLocal() as db:
        auth_service.consume_token(db, first_token, "verify")

    with _SessionLocal() as db:
        row = db.query(AuthToken).filter(AuthToken.user_id == user.id).one()
        used_at_from_consumption = row.used_at
        assert used_at_from_consumption is not None

    with _SessionLocal() as db:
        auth_service.issue_verification_token(db, user)

    with _SessionLocal() as db:
        row = (
            db.query(AuthToken)
            .filter(AuthToken.token_hash == auth_service._hash_token(first_token))
            .one()
        )
        assert row.used_at == used_at_from_consumption


def test_reissuing_does_not_touch_a_token_of_a_different_purpose():
    """A password-reset token for the same user must survive a verification
    resend -- the invalidation is scoped by purpose, not just by user."""
    user = _make_user()
    with _SessionLocal() as db:
        reset_token = auth_service.issue_password_reset_token(db, user)
    with _SessionLocal() as db:
        auth_service.issue_verification_token(db, user)

    with _SessionLocal() as db:
        reset_user = auth_service.consume_token(db, reset_token, "password_reset")
        assert reset_user.id == user.id


# -------------------------------------------------------- consume_token ---


def test_consume_token_returns_the_owning_user_and_marks_it_used():
    user = _make_user()
    with _SessionLocal() as db:
        raw_token = auth_service.issue_verification_token(db, user)

    with _SessionLocal() as db:
        returned_user = auth_service.consume_token(db, raw_token, "verify")
        assert returned_user.id == user.id

    with _SessionLocal() as db:
        row = db.query(AuthToken).filter(AuthToken.user_id == user.id).one()
        assert row.used_at is not None


def test_consume_token_rejects_an_unknown_token():
    with _SessionLocal() as db:
        with pytest.raises(auth_service.TokenError):
            auth_service.consume_token(db, "this-token-was-never-issued", "verify")


def test_consume_token_rejects_a_token_already_used():
    user = _make_user()
    with _SessionLocal() as db:
        raw_token = auth_service.issue_verification_token(db, user)
    with _SessionLocal() as db:
        auth_service.consume_token(db, raw_token, "verify")

    with _SessionLocal() as db:
        with pytest.raises(auth_service.TokenError):
            auth_service.consume_token(db, raw_token, "verify")


def test_consume_token_rejects_an_expired_token():
    user = _make_user()
    with _SessionLocal() as db:
        raw_token = auth_service.issue_verification_token(db, user)

    with _SessionLocal() as db:
        row = db.query(AuthToken).filter(AuthToken.user_id == user.id).one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.add(row)
        db.commit()

    with _SessionLocal() as db:
        with pytest.raises(auth_service.TokenError):
            auth_service.consume_token(db, raw_token, "verify")


def test_consume_token_rejects_the_right_token_for_the_wrong_purpose():
    """A verification token must not double as a password-reset token even
    though both are rows in the same table."""
    user = _make_user()
    with _SessionLocal() as db:
        raw_token = auth_service.issue_verification_token(db, user)

    with _SessionLocal() as db:
        with pytest.raises(auth_service.TokenError):
            auth_service.consume_token(db, raw_token, "password_reset")


def test_consume_token_rejects_a_token_whose_user_no_longer_exists():
    """Defensive branch: a token row can outlive its user if the owning row
    is removed by something other than the ORM-level cascade (a bulk
    delete, a manual cleanup job). consume_token must still fail closed --
    never resolve to no user, or a caller that forgets to check for `None`
    would treat the token as valid."""
    user = _make_user()
    with _SessionLocal() as db:
        raw_token = auth_service.issue_verification_token(db, user)

    with _SessionLocal() as db:
        # A bulk delete bypasses SQLAlchemy's ORM-level cascade (which only
        # fires for `session.delete(obj)`), leaving the token row orphaned --
        # exactly the state this branch guards against.
        db.query(User).filter(User.id == user.id).delete()
        db.commit()

    with _SessionLocal() as db:
        with pytest.raises(auth_service.TokenError):
            auth_service.consume_token(db, raw_token, "verify")


# -------------------------------------------------------------- emails ---


def test_send_verification_email_delivers_the_token_to_the_users_address():
    user = _make_user(email="verify-me@example.com")
    with _SessionLocal() as db:
        raw_token = auth_service.issue_verification_token(db, user)

    auth_service.send_verification_email(user, raw_token)

    assert len(mailer.OUTBOX) == 1
    sent = mailer.OUTBOX[-1]
    assert sent.to == "verify-me@example.com"
    assert sent.subject == "Verify your email"
    assert raw_token in sent.body


def test_send_password_reset_email_delivers_the_token_to_the_users_address():
    user = _make_user(email="reset-me@example.com")
    with _SessionLocal() as db:
        raw_token = auth_service.issue_password_reset_token(db, user)

    auth_service.send_password_reset_email(user, raw_token)

    assert len(mailer.OUTBOX) == 1
    sent = mailer.OUTBOX[-1]
    assert sent.to == "reset-me@example.com"
    assert sent.subject == "Reset your password"
    assert raw_token in sent.body


def test_verification_and_reset_emails_are_not_interchangeable():
    """A reset email must not carry language that reads as an account
    verification, and vice versa -- these are sent for different reasons and
    a mixed-up body would mislead whichever user receives it."""
    user = _make_user(email="distinct@example.com")
    with _SessionLocal() as db:
        verify_token = auth_service.issue_verification_token(db, user)
    with _SessionLocal() as db:
        reset_token = auth_service.issue_password_reset_token(db, user)

    auth_service.send_verification_email(user, verify_token)
    auth_service.send_password_reset_email(user, reset_token)

    assert len(mailer.OUTBOX) == 2
    verify_sent, reset_sent = mailer.OUTBOX
    assert verify_sent.subject != reset_sent.subject
    assert reset_token not in verify_sent.body
    assert verify_token not in reset_sent.body
