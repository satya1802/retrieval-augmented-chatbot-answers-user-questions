"""Tests for GET /me/usage (app/routers/me.py, AC-013).

test_documents.py already covers the happy path (`document_count` present,
`documents_cap` matching config, auth required). This file covers what that
one leaves untouched: the window rollover `GET /me/usage` must mirror from
`enforce_question_capacity`, the `remaining_questions` arithmetic and its
zero-clamp, that `document_count` is scoped to the caller alone (not every
document in the table), and the 404 a deleted-but-still-bearer-token'd
caller gets.
"""

from datetime import date, timedelta

import pytest

from app.database import Base, engine
from app.database import SessionLocal as _SessionLocal
from app.models import User
from app.services.usage_service import QUESTION_WINDOW_DAYS
from app.services import mailer


@pytest.fixture(autouse=True)
def _clean_state():
    mailer.OUTBOX.clear()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


def _latest_token() -> str:
    assert mailer.OUTBOX, "no email was sent"
    return mailer.OUTBOX[-1].body.rsplit(" ", 1)[-1].strip()


def _auth_headers(client, email="owner@example.com", password="Password1") -> dict:
    client.post("/auth/register", json={"email": email, "password": password})
    token = _latest_token()
    client.post("/auth/verify", json={"token": token})
    login = client.post("/auth/login", json={"email": email, "password": password})
    access_token = login.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def _set_user(email: str, **fields) -> None:
    with _SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        for key, value in fields.items():
            setattr(user, key, value)
        db.add(user)
        db.commit()


def _get_user(email: str) -> User:
    with _SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        db.expunge(user)
        return user


# ----------------------------------------------------------- AC-013 -------


def test_remaining_questions_reflects_questions_already_used(client):
    from app.config import MONTHLY_QUESTION_CAP

    headers = _auth_headers(client, "used@example.com")
    _set_user("used@example.com", monthly_question_count=5)

    resp = client.get("/me/usage", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["remaining_questions"] == MONTHLY_QUESTION_CAP - 5


def test_remaining_questions_never_reports_negative(client):
    from app.config import MONTHLY_QUESTION_CAP

    headers = _auth_headers(client, "over@example.com")
    _set_user("over@example.com", monthly_question_count=MONTHLY_QUESTION_CAP + 10)

    resp = client.get("/me/usage", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["remaining_questions"] == 0


def test_expired_window_rolls_over_before_usage_is_reported(client):
    """`GET /me/usage` must never report a stale count or an already-past
    reset_date for a window that `enforce_question_capacity` would already
    have rolled over before the next question -- it shares the same
    rollover helper for exactly this reason."""
    from app.config import MONTHLY_QUESTION_CAP

    headers = _auth_headers(client, "stale@example.com")
    stale_start = date.today() - timedelta(days=QUESTION_WINDOW_DAYS + 5)
    _set_user(
        "stale@example.com",
        monthly_question_count=MONTHLY_QUESTION_CAP,
        question_window_start=stale_start,
    )

    resp = client.get("/me/usage", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    # The window rolled over: full cap available again, not zero.
    assert body["remaining_questions"] == MONTHLY_QUESTION_CAP
    assert date.fromisoformat(body["reset_date"]) >= date.today()

    # The rollover was persisted, not just reflected in this one response.
    persisted = _get_user("stale@example.com")
    assert persisted.monthly_question_count == 0
    assert persisted.question_window_start == date.today()


def test_current_window_reset_date_is_window_start_plus_window_length(client):
    headers = _auth_headers(client, "window@example.com")
    start = date.today() - timedelta(days=3)
    _set_user("window@example.com", question_window_start=start)

    resp = client.get("/me/usage", headers=headers)
    assert resp.status_code == 200
    expected = start + timedelta(days=QUESTION_WINDOW_DAYS)
    assert date.fromisoformat(resp.json()["reset_date"]) == expected


def test_document_count_is_scoped_to_the_caller_not_every_document(client):
    owner_headers = _auth_headers(client, "docowner@example.com")
    other_headers = _auth_headers(client, "docother@example.com")

    client.post(
        "/documents",
        headers=owner_headers,
        files=[("files", ("mine.txt", b"owner content", "text/plain"))],
    )
    client.post(
        "/documents",
        headers=other_headers,
        files=[("files", ("a.txt", b"other content a", "text/plain"))],
    )
    client.post(
        "/documents",
        headers=other_headers,
        files=[("files", ("b.txt", b"other content b", "text/plain"))],
    )

    owner_usage = client.get("/me/usage", headers=owner_headers).json()
    other_usage = client.get("/me/usage", headers=other_headers).json()

    assert owner_usage["document_count"] == 1
    assert other_usage["document_count"] == 2


def test_documents_cap_in_response_reflects_the_single_configurable_setting(client, monkeypatch):
    import app.routers.me as me_module

    monkeypatch.setattr(me_module, "DOCUMENTS_CAP", 7)
    headers = _auth_headers(client, "cap@example.com")

    resp = client.get("/me/usage", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["documents_cap"] == 7


def test_usage_for_deleted_user_is_404(client):
    """A caller whose bearer token is still valid, but whose account row no
    longer exists, gets 404 rather than a response built from a None user."""
    headers = _auth_headers(client, "ghost@example.com")

    with _SessionLocal() as db:
        user = db.query(User).filter(User.email == "ghost@example.com").one()
        db.delete(user)
        db.commit()

    resp = client.get("/me/usage", headers=headers)
    assert resp.status_code == 404


def test_usage_rejects_missing_or_invalid_token(client):
    missing = client.get("/me/usage")
    assert missing.status_code == 401

    bad = client.get("/me/usage", headers={"Authorization": "Bearer not-a-real-token"})
    assert bad.status_code == 401
