"""Unit tests for app/services/usage_service.py.

These exercise the service directly against a real session (SessionLocal/
engine, the same database the HTTP layer uses) rather than going back through
a router, so they fail on a break in the cap arithmetic itself, independent
of the HTTP-level integration already covered in test_documents.py (the
document cap, AC-011) and test_conversations.py (the monthly question cap,
AC-012). Only the module's public functions are exercised -- the private
`_roll_window_if_expired` helper is covered indirectly through
`enforce_question_capacity`, the only thing that calls it.
"""

import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.database import Base, SessionLocal, engine
from app.models import Document, User
from app.services import usage_service


@pytest.fixture(autouse=True)
def _clean_state():
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_user(db, email="user@example.com", *, count=0, window_start=None) -> User:
    user = User(
        email=email,
        password_hash="hashed",
        is_verified=True,
        monthly_question_count=count,
        question_window_start=window_start or date.today(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_document(db, owner_id, title="doc") -> Document:
    doc = Document(
        owner_id=owner_id,
        title=title,
        file_type="txt",
        storage_key=f"storage/{uuid.uuid4()}",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _reload_user(email: str) -> User:
    session = SessionLocal()
    try:
        return session.query(User).filter(User.email == email).one()
    finally:
        session.close()


# -------------------------------------------------- check_document_capacity


def test_check_document_capacity_allows_upload_under_the_cap(db):
    user = _make_user(db)
    _make_document(db, user.id)

    # One document already stored; one more fits comfortably under a cap
    # of 5. No exception means the upload is allowed.
    usage_service.check_document_capacity(db, user.id, additional=1, cap=5)


def test_check_document_capacity_allows_exactly_reaching_the_cap(db):
    user = _make_user(db)
    _make_document(db, user.id)

    # 1 existing + 1 additional == cap of 2: landing exactly on the cap is
    # allowed, the refusal is only for going *over* it.
    usage_service.check_document_capacity(db, user.id, additional=1, cap=2)


def test_check_document_capacity_refuses_with_409_naming_the_cap(db):
    user = _make_user(db)
    _make_document(db, user.id)

    with pytest.raises(HTTPException) as exc_info:
        usage_service.check_document_capacity(db, user.id, additional=1, cap=1)

    assert exc_info.value.status_code == 409
    assert "1" in exc_info.value.detail
    assert "delete" in exc_info.value.detail.lower()


def test_check_document_capacity_counts_every_file_in_a_multi_file_batch(db):
    user = _make_user(db)
    _make_document(db, user.id)

    # 1 existing + 3 additional (one multi-file upload request) exceeds a
    # cap of 2, even though no single file alone would.
    with pytest.raises(HTTPException) as exc_info:
        usage_service.check_document_capacity(db, user.id, additional=3, cap=2)
    assert exc_info.value.status_code == 409


def test_check_document_capacity_is_scoped_to_the_owner(db):
    owner = _make_user(db, "owner@example.com")
    other = _make_user(db, "other@example.com")
    _make_document(db, owner.id)
    _make_document(db, owner.id)

    # `owner` is already over a cap of 1, but `other` has no documents of
    # their own -- the count must not leak across owners.
    usage_service.check_document_capacity(db, other.id, additional=1, cap=1)


def test_check_document_capacity_default_cap_is_the_configured_documents_cap(db):
    from app.config import DOCUMENTS_CAP

    # The default argument is bound to app.config.DOCUMENTS_CAP at import
    # time (see the router docstrings' note that the cap is passed in
    # explicitly, not re-read from the module at call time); assert the two
    # actually agree rather than trusting the import alone.
    assert usage_service.check_document_capacity.__defaults__[-1] == DOCUMENTS_CAP


# -------------------------------------------------------- question_reset_date


def test_question_reset_date_is_30_days_after_the_window_start(db):
    user = _make_user(db, window_start=date(2026, 1, 1))
    assert usage_service.question_reset_date(user) == date(2026, 1, 31)


# ------------------------------------------------------ enforce_question_capacity


def test_enforce_question_capacity_allows_a_question_under_the_cap(db):
    user = _make_user(db, count=2)

    usage_service.enforce_question_capacity(db, user, cap=5)

    assert _reload_user(user.email).monthly_question_count == 2


def test_enforce_question_capacity_refuses_with_409_naming_the_limit_and_reset_date(db):
    # window_start is "today", well inside the 30-day window, so the
    # refusal is the cap being spent -- not an unrelated rollover.
    window_start = date.today()
    user = _make_user(db, count=3, window_start=window_start)

    with pytest.raises(HTTPException) as exc_info:
        usage_service.enforce_question_capacity(db, user, cap=3)

    assert exc_info.value.status_code == 409
    assert "3" in exc_info.value.detail
    expected_reset = (window_start + timedelta(days=usage_service.QUESTION_WINDOW_DAYS)).isoformat()
    assert expected_reset in exc_info.value.detail


def test_enforce_question_capacity_allows_the_question_one_short_of_the_cap(db):
    # Using 2 of a cap of 3 still leaves room; the refusal only fires once
    # the count has actually reached the cap, not one below it.
    user = _make_user(db, count=2)
    usage_service.enforce_question_capacity(db, user, cap=3)


def test_enforce_question_capacity_rolls_over_a_window_exactly_30_days_old(db):
    user = _make_user(db, count=5, window_start=date.today() - timedelta(days=30))

    # A 30-day-old window must roll over -- and therefore allow the
    # question -- even though its (now-stale) count was already at the cap.
    usage_service.enforce_question_capacity(db, user, cap=5)

    reloaded = _reload_user(user.email)
    assert reloaded.monthly_question_count == 0
    assert reloaded.question_window_start == date.today()


def test_enforce_question_capacity_does_not_roll_over_a_window_one_day_short(db):
    window_start = date.today() - timedelta(days=29)
    user = _make_user(db, count=5, window_start=window_start)

    with pytest.raises(HTTPException):
        usage_service.enforce_question_capacity(db, user, cap=5)

    reloaded = _reload_user(user.email)
    assert reloaded.monthly_question_count == 5
    assert reloaded.question_window_start == window_start


def test_enforce_question_capacity_persists_a_rollover_that_still_allows_the_question(db):
    """A rolled-over window must be saved even when the now-reset count
    clears the cap on this very call, not only when it still refuses."""
    user = _make_user(db, count=5, window_start=date.today() - timedelta(days=45))

    usage_service.enforce_question_capacity(db, user, cap=5)

    reloaded = _reload_user(user.email)
    assert reloaded.monthly_question_count == 0
    assert reloaded.question_window_start == date.today()


# -------------------------------------------------------- increment_question_count


def test_increment_question_count_increments_and_persists(db):
    user = _make_user(db, count=4)

    usage_service.increment_question_count(db, user)

    assert user.monthly_question_count == 5
    assert _reload_user(user.email).monthly_question_count == 5


def test_increment_question_count_accumulates_across_repeated_calls(db):
    user = _make_user(db, count=0)

    usage_service.increment_question_count(db, user)
    usage_service.increment_question_count(db, user)
    usage_service.increment_question_count(db, user)

    assert _reload_user(user.email).monthly_question_count == 3
