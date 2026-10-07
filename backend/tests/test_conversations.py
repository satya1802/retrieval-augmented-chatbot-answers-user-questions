"""Tests for app/routers/conversations.py.

Covers, through the HTTP layer (TestClient against the real app, exactly as
test_documents.py and test_chunks.py do), every behaviour the router's
docstrings claim:

* auth is required on every route (AC-010, via app.security)
* list/get/ask are scoped to the caller's own conversations, 404 on a
  mismatch, never 403 (AC-073, AC-075, AC-008)
* create accepts an optional document scope (AC-039, AC-076)
* ask_question enforces the monthly question cap *before* retrieval or the
  (not-yet-built) generation pipeline runs, rolls the window over when it
  has expired, counts a question that clears the cap, and scopes the
  context-chunk query to the caller (AC-012, AC-009)
* the still-unbuilt generation pipeline answers 501, not a success, so no
  caller can mistake the stub for a real answer
"""

import datetime as dt
import uuid
from datetime import date, timedelta

import pytest

from app.database import Base, SessionLocal, engine
from app.models import Conversation, Message, User
from app.routers import conversations as conversations_router
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


def _get_user(email: str) -> User:
    session = SessionLocal()
    try:
        return session.query(User).filter(User.email == email).one()
    finally:
        session.close()


def _set_user_usage(email: str, *, count: int, window_start: date) -> None:
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.email == email).one()
        user.monthly_question_count = count
        user.question_window_start = window_start
        session.add(user)
        session.commit()
    finally:
        session.close()


def _make_conversation(owner_email: str, *, title=None, scope_document_ids=None, created_at=None):
    session = SessionLocal()
    try:
        owner = session.query(User).filter(User.email == owner_email).one()
        kwargs = {}
        if scope_document_ids is not None:
            kwargs["scope_document_ids"] = scope_document_ids
        if created_at is not None:
            kwargs["created_at"] = created_at
        convo = Conversation(owner_id=owner.id, title=title, **kwargs)
        session.add(convo)
        session.commit()
        session.refresh(convo)
        return convo
    finally:
        session.close()


def _make_message(conversation_id, role="user", content="hello"):
    session = SessionLocal()
    try:
        message = Message(conversation_id=conversation_id, role=role, content=content)
        session.add(message)
        session.commit()
        session.refresh(message)
        return message
    finally:
        session.close()


def _ask(client, headers, conversation_id, question="What does the doc say?"):
    return client.post(
        f"/conversations/{conversation_id}/messages",
        json={"question": question},
        headers=headers,
    )


# -------------------------------------------------------- authentication --


def test_conversations_routes_require_auth(client):
    assert client.get("/conversations").status_code == 401
    assert client.post("/conversations", json={}).status_code == 401
    assert client.get("/conversations/11111111-1111-1111-1111-111111111111").status_code == 401
    resp = client.post(
        "/conversations/11111111-1111-1111-1111-111111111111/messages",
        json={"question": "hi"},
    )
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


def test_invalid_token_is_rejected(client):
    resp = client.get("/conversations", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


# ------------------------------------------------------ list_conversations


def test_list_conversations_returns_only_the_callers_own(client):
    owner_headers = _auth_headers(client, "owner@example.com")
    _auth_headers(client, "stranger@example.com")
    mine = _make_conversation("owner@example.com", title="mine")
    _make_conversation("stranger@example.com", title="not mine")

    resp = client.get("/conversations", headers=owner_headers)

    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["conversations"]]
    assert ids == [str(mine.id)]


def test_list_conversations_orders_most_recent_first(client):
    owner_headers = _auth_headers(client, "owner@example.com")
    _make_conversation("owner@example.com", title="older", created_at=dt.datetime(2020, 1, 1))
    _make_conversation("owner@example.com", title="newer", created_at=dt.datetime(2030, 1, 1))

    resp = client.get("/conversations", headers=owner_headers)

    titles = [c["title"] for c in resp.json()["conversations"]]
    assert titles == ["newer", "older"]


# ---------------------------------------------------------- create -------


def test_create_conversation_with_no_scope(client):
    headers = _auth_headers(client, "owner@example.com")

    resp = client.post("/conversations", json={"title": "General"}, headers=headers)

    assert resp.status_code == 201
    body = resp.json()["conversation"]
    assert body["title"] == "General"
    assert body["scope_document_ids"] == []


def test_create_conversation_with_document_scope(client):
    headers = _auth_headers(client, "owner@example.com")
    doc_id = "11111111-1111-1111-1111-111111111111"

    resp = client.post(
        "/conversations",
        json={"title": "Scoped", "scope_document_ids": [doc_id]},
        headers=headers,
    )

    assert resp.status_code == 201
    assert resp.json()["conversation"]["scope_document_ids"] == [doc_id]


def test_created_conversation_is_owned_by_the_caller(client):
    headers = _auth_headers(client, "owner@example.com")

    resp = client.post("/conversations", json={}, headers=headers)
    conversation_id = resp.json()["conversation"]["id"]

    owner = _get_user("owner@example.com")
    session = SessionLocal()
    try:
        # The id round-trips through JSON as a string; the primary key
        # column needs an actual uuid.UUID to look it up.
        stored = session.get(Conversation, uuid.UUID(conversation_id))
        assert str(stored.owner_id) == str(owner.id)
    finally:
        session.close()


# ------------------------------------------------------- get_conversation


def test_get_conversation_returns_its_messages(client):
    headers = _auth_headers(client, "owner@example.com")
    convo = _make_conversation("owner@example.com", title="with history")
    _make_message(convo.id, role="user", content="hello")

    resp = client.get(f"/conversations/{convo.id}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation"]["id"] == str(convo.id)
    assert len(body["messages"]) == 1
    assert body["messages"][0]["content"] == "hello"


def test_get_conversation_404_for_another_users_conversation(client):
    _auth_headers(client, "owner@example.com")
    stranger_headers = _auth_headers(client, "stranger@example.com")
    convo = _make_conversation("owner@example.com")

    resp = client.get(f"/conversations/{convo.id}", headers=stranger_headers)

    # Never 403: a 403 body would confirm the resource exists at all.
    assert resp.status_code == 404


def test_get_conversation_404_for_nonexistent_id(client):
    headers = _auth_headers(client, "owner@example.com")

    resp = client.get(
        "/conversations/00000000-0000-0000-0000-000000000000", headers=headers
    )

    assert resp.status_code == 404


# -------------------------------------------------------- ask_question ---


def test_ask_question_404_for_another_users_conversation(client):
    _auth_headers(client, "owner@example.com")
    stranger_headers = _auth_headers(client, "stranger@example.com")
    convo = _make_conversation("owner@example.com")

    resp = _ask(client, stranger_headers, convo.id)

    assert resp.status_code == 404


def test_ask_question_404_for_nonexistent_conversation(client):
    """Same owner-scoped 404 as GET /conversations/{id} (AC-008), exercised
    on the ask endpoint specifically -- this is the route that must refuse
    before the cap is touched or any retrieval runs."""
    headers = _auth_headers(client, "owner@example.com")

    resp = _ask(client, headers, "00000000-0000-0000-0000-000000000000")

    assert resp.status_code == 404


def test_ask_question_rejects_empty_question(client):
    headers = _auth_headers(client, "owner@example.com")
    convo = _make_conversation("owner@example.com")

    resp = _ask(client, headers, convo.id, question="")

    assert resp.status_code == 422


def test_ask_question_answers_501_stub(client):
    """The generation pipeline doesn't exist yet -- the handler must refuse
    with 501, never a fabricated success, so no caller mistakes the stub
    for a real answer."""
    headers = _auth_headers(client, "owner@example.com")
    convo = _make_conversation("owner@example.com")

    resp = _ask(client, headers, convo.id)

    assert resp.status_code == 501
    assert resp.json()["detail"] == conversations_router._NOT_IMPLEMENTED


def test_ask_question_enforces_cap_before_any_processing(client, monkeypatch):
    """AC-012: a caller who has already spent the monthly cap is refused
    with 409 naming the limit, and the (stubbed) retrieval step never runs
    once the cap is exhausted."""
    monkeypatch.setattr(conversations_router, "MONTHLY_QUESTION_CAP", 1)
    calls = []
    monkeypatch.setattr(
        conversations_router,
        "build_context_chunk_query",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    headers = _auth_headers(client, "owner@example.com")
    convo = _make_conversation("owner@example.com")

    first = _ask(client, headers, convo.id)
    assert first.status_code == 501
    assert len(calls) == 1

    second = _ask(client, headers, convo.id)
    assert second.status_code == 409
    assert "Monthly question limit of 1" in second.json()["detail"]
    # The retrieval step must not have been reached a second time.
    assert len(calls) == 1


def test_ask_question_cap_refusal_names_the_reset_date(client, monkeypatch):
    """The 409 body must be actionable, not just a dead end: it names both
    the limit (covered above) and the date the window resets."""
    monkeypatch.setattr(conversations_router, "MONTHLY_QUESTION_CAP", 1)
    headers = _auth_headers(client, "owner@example.com")
    _set_user_usage("owner@example.com", count=1, window_start=date.today())
    convo = _make_conversation("owner@example.com")

    resp = _ask(client, headers, convo.id)

    assert resp.status_code == 409
    user = _get_user("owner@example.com")
    from app.services.usage_service import question_reset_date

    assert question_reset_date(user).isoformat() in resp.json()["detail"]


def test_ask_question_increments_count_on_a_question_that_clears_the_cap(client, monkeypatch):
    monkeypatch.setattr(conversations_router, "MONTHLY_QUESTION_CAP", 5)
    headers = _auth_headers(client, "owner@example.com")
    convo = _make_conversation("owner@example.com")

    resp = _ask(client, headers, convo.id)

    assert resp.status_code == 501
    assert _get_user("owner@example.com").monthly_question_count == 1


def test_ask_question_rolls_over_an_expired_window(client, monkeypatch):
    """A caller who exhausted the cap last window is not stuck forever:
    once the 30-day window has elapsed, the count resets and the question
    is answered (with the stub's 501, not a 409) again."""
    monkeypatch.setattr(conversations_router, "MONTHLY_QUESTION_CAP", 1)
    headers = _auth_headers(client, "owner@example.com")
    _set_user_usage(
        "owner@example.com", count=1, window_start=date.today() - timedelta(days=31)
    )
    convo = _make_conversation("owner@example.com")

    resp = _ask(client, headers, convo.id)

    assert resp.status_code == 501
    user = _get_user("owner@example.com")
    assert user.monthly_question_count == 1
    assert user.question_window_start == date.today()


def test_ask_question_scopes_retrieval_to_the_callers_conversation_scope(client, monkeypatch):
    """AC-009: the context-chunk query is built with the caller's own
    owner_id, and with the conversation's scope_document_ids when it has
    one -- not a blanket, unscoped query."""
    captured = {}

    def _fake_query(db, owner_id, document_ids=None, **kwargs):
        captured["owner_id"] = owner_id
        captured["document_ids"] = document_ids

    monkeypatch.setattr(conversations_router, "build_context_chunk_query", _fake_query)

    headers = _auth_headers(client, "owner@example.com")
    doc_id = "22222222-2222-2222-2222-222222222222"
    convo = _make_conversation("owner@example.com", scope_document_ids=[doc_id])

    resp = _ask(client, headers, convo.id)

    assert resp.status_code == 501
    owner = _get_user("owner@example.com")
    assert str(captured["owner_id"]) == str(owner.id)
    assert [str(d) for d in captured["document_ids"]] == [doc_id]


def test_ask_question_retrieval_scope_is_none_without_a_conversation_scope(client, monkeypatch):
    captured = {}

    def _fake_query(db, owner_id, document_ids=None, **kwargs):
        captured["document_ids"] = document_ids

    monkeypatch.setattr(conversations_router, "build_context_chunk_query", _fake_query)

    headers = _auth_headers(client, "owner@example.com")
    convo = _make_conversation("owner@example.com")

    resp = _ask(client, headers, convo.id)

    assert resp.status_code == 501
    assert captured["document_ids"] is None
