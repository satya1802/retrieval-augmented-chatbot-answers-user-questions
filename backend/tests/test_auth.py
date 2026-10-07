"""Behavioural tests for the auth service: register, verify, login, reset."""

from datetime import UTC, datetime, timedelta

import pytest

from app.database import Base, engine
from app.database import SessionLocal as _SessionLocal
from app.models import AuthToken, User
from app.security import PASSWORD_MIN_LENGTH, PASSWORD_RULE, validate_password_strength
from app.services import mailer


@pytest.fixture(autouse=True)
def _clean_state():
    mailer.OUTBOX.clear()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


def _register(client, email="user@example.com", password="Password1"):
    return client.post("/auth/register", json={"email": email, "password": password})


def _latest_token() -> str:
    assert mailer.OUTBOX, "no email was sent"
    return mailer.OUTBOX[-1].body.rsplit(" ", 1)[-1].strip()


# ----------------------------------------------------------- AC-001 -------


def test_register_creates_unverified_user_and_sends_verification_email(client):
    resp = _register(client, "new@example.com", "Password1")

    assert resp.status_code == 202
    assert len(mailer.OUTBOX) == 1
    assert mailer.OUTBOX[-1].to == "new@example.com"

    with _SessionLocal() as db:
        user = db.query(User).filter(User.email == "new@example.com").one()
        assert user.is_verified is False
        assert user.password_hash != "Password1"  # never stored plaintext


def test_register_rejects_a_weak_password(client):
    resp = _register(client, "weak@example.com", "short")
    assert resp.status_code == 422
    assert mailer.OUTBOX == []


# ----------------------------------------------------------- AC-002 -------


def test_verify_with_valid_token_marks_verified_and_allows_login(client):
    _register(client, "verify@example.com", "Password1")
    token = _latest_token()

    resp = client.post("/auth/verify", json={"token": token})
    assert resp.status_code == 200
    assert resp.json() == {"verified": True}

    login = client.post(
        "/auth/login", json={"email": "verify@example.com", "password": "Password1"}
    )
    assert login.status_code == 200
    assert "access_token" in login.json()


def test_verify_rejects_unknown_token(client):
    resp = client.post("/auth/verify", json={"token": "not-a-real-token"})
    assert resp.status_code == 400


def test_expired_verification_token_is_rejected(client):
    _register(client, "expired@example.com", "Password1")
    token = _latest_token()

    with _SessionLocal() as db:
        auth_token = db.query(AuthToken).order_by(AuthToken.expires_at.desc()).first()
        auth_token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.add(auth_token)
        db.commit()

    resp = client.post("/auth/verify", json={"token": token})
    assert resp.status_code == 400


# ----------------------------------------------------------- AC-003 -------


def test_register_existing_email_is_identical_and_creates_no_second_account(client):
    first = _register(client, "dup@example.com", "Password1")
    second = _register(client, "dup@example.com", "Password1")

    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()

    with _SessionLocal() as db:
        count = db.query(User).filter(User.email == "dup@example.com").count()
    assert count == 1


def test_register_for_already_verified_email_is_identical_response(client):
    first = _register(client, "already@example.com", "Password1")
    client.post("/auth/verify", json={"token": _latest_token()})

    again = _register(client, "already@example.com", "Password1")
    assert again.status_code == 202
    assert again.json() == first.json()


# ----------------------------------------------------------- AC-004 -------


def test_login_unverified_is_refused_and_resend_invalidates_earlier_token(client):
    _register(client, "resend@example.com", "Password1")
    old_token = _latest_token()

    login = client.post(
        "/auth/login", json={"email": "resend@example.com", "password": "Password1"}
    )
    assert login.status_code == 403
    detail = login.json()["detail"]
    assert detail["verification_required"] is True
    assert "resend_path" in detail

    mailer.OUTBOX.clear()
    _register(client, "resend@example.com", "Password1")
    new_token = _latest_token()
    assert new_token != old_token

    stale = client.post("/auth/verify", json={"token": old_token})
    assert stale.status_code == 400

    fresh = client.post("/auth/verify", json={"token": new_token})
    assert fresh.status_code == 200

    login_ok = client.post(
        "/auth/login", json={"email": "resend@example.com", "password": "Password1"}
    )
    assert login_ok.status_code == 200


# ----------------------------------------------------------- AC-005 -------


def test_login_with_correct_credentials_returns_a_jwt_with_expiry(client):
    import jwt as pyjwt

    from app.security import JWT_ALGORITHM, JWT_SECRET

    _register(client, "login@example.com", "Password1")
    client.post("/auth/verify", json={"token": _latest_token()})

    resp = client.post("/auth/login", json={"email": "login@example.com", "password": "Password1"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert "sub" in payload
    assert "exp" in payload

    with _SessionLocal() as db:
        user = db.query(User).filter(User.email == "login@example.com").one()
        assert payload["sub"] == str(user.id)


# ----------------------------------------------------------- AC-006 -------


def test_login_wrong_password_and_unknown_email_both_generic_401(client):
    _register(client, "known@example.com", "Password1")
    client.post("/auth/verify", json={"token": _latest_token()})

    wrong = client.post(
        "/auth/login", json={"email": "known@example.com", "password": "WrongPass1"}
    )
    unknown = client.post(
        "/auth/login", json={"email": "nope@example.com", "password": "WrongPass1"}
    )

    assert wrong.status_code == 401
    assert unknown.status_code == 401
    assert wrong.json()["detail"] == "invalid email or password"
    assert unknown.json()["detail"] == "invalid email or password"


# ----------------------------------------------------------- AC-007 -------


def test_password_reset_request_always_202(client):
    _register(client, "haveacct@example.com", "Password1")

    known = client.post("/auth/password-reset/request", json={"email": "haveacct@example.com"})
    unknown = client.post("/auth/password-reset/request", json={"email": "ghost@example.com"})

    assert known.status_code == 202
    assert unknown.status_code == 202
    assert known.json() == unknown.json()


def test_password_reset_confirm_sets_password_and_token_is_single_use(client):
    _register(client, "reset@example.com", "Password1")
    client.post("/auth/verify", json={"token": _latest_token()})

    mailer.OUTBOX.clear()
    client.post("/auth/password-reset/request", json={"email": "reset@example.com"})
    reset_token = _latest_token()

    confirm = client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "NewPassword1"},
    )
    assert confirm.status_code == 200

    reuse = client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "AnotherPass1"},
    )
    assert reuse.status_code == 400

    old_login = client.post(
        "/auth/login", json={"email": "reset@example.com", "password": "Password1"}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login", json={"email": "reset@example.com", "password": "NewPassword1"}
    )
    assert new_login.status_code == 200


def test_password_reset_confirm_rejects_weak_new_password(client):
    _register(client, "weakreset@example.com", "Password1")
    client.post("/auth/verify", json={"token": _latest_token()})

    mailer.OUTBOX.clear()
    client.post("/auth/password-reset/request", json={"email": "weakreset@example.com"})
    reset_token = _latest_token()

    resp = client.post(
        "/auth/password-reset/confirm", json={"token": reset_token, "new_password": "weak"}
    )
    assert resp.status_code == 422


# ------------------------------------------------------ password rules ---


def test_password_rule_is_a_single_constant_the_frontend_can_mirror():
    assert PASSWORD_MIN_LENGTH >= 8
    assert isinstance(PASSWORD_RULE, str) and PASSWORD_RULE


def test_validate_password_strength_enforces_the_rule():
    with pytest.raises(ValueError):
        validate_password_strength("short1")
    with pytest.raises(ValueError):
        validate_password_strength("alllettersnodigits")
    with pytest.raises(ValueError):
        validate_password_strength("12345678")
    validate_password_strength("Password1")  # does not raise
