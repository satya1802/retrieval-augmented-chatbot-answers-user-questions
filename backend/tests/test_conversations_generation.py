"""Tests for the grounded answer-generation pipeline (US-014-1)."""

import uuid

import pytest

from app.database import Base, SessionLocal, engine
from app.models import Chunk, Document, User
from app.routers.conversations import EMPTY_LIBRARY_MESSAGE, INSUFFICIENT_CONTEXT_MESSAGE
from app.services import mailer
from app.services.generation_client import GenerationError, set_generation_client

PARIS_TEXT = "Paris is the capital of France. It sits on the river Seine."
UNRELATED_TEXT = "The office cafeteria serves lunch between noon and two o'clock."


@pytest.fixture(autouse=True)
def _clean_state():
    mailer.OUTBOX.clear()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    set_generation_client(None)
    yield
    set_generation_client(None)


def _latest_token() -> str:
    assert mailer.OUTBOX, "no email was sent"
    return mailer.OUTBOX[-1].body.rsplit(" ", 1)[-1].strip()


def _auth(client, email="asker@example.com", password="Password1") -> tuple[dict, uuid.UUID]:
    client.post("/auth/register", json={"email": email, "password": password})
    token = _latest_token()
    client.post("/auth/verify", json={"token": token})
    login = client.post("/auth/login", json={"email": email, "password": password})
    access_token = login.json()["access_token"]
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email.lower()).one()
        user_id = user.id
    return {"Authorization": f"Bearer {access_token}"}, user_id


def _ready_document_with_chunk(owner_id: uuid.UUID, text: str) -> None:
    with SessionLocal() as db:
        document = Document(
            owner_id=owner_id,
            title="doc.txt",
            file_type="txt",
            storage_key="unused",
            status="ready",
        )
        db.add(document)
        db.flush()
        chunk = Chunk(
            document_id=document.id,
            owner_id=owner_id,
            position=0,
            text=text,
            embedding=[1.0, 0.0, 0.0],
        )
        db.add(chunk)
        db.commit()


class _FakeEmbeddingClient:
    """Embeds every question to the same vector, so whatever ready chunks
    exist are the retrieval candidates -- scoring is irrelevant to these
    tests; only what gets passed to generation and what it returns does."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class _GroundedFakeGenerationClient:
    """Returns an answer built only from the supplied context, never from
    the question's own wording -- proof the pipeline passes chunks, not
    general knowledge, to the provider."""

    def __init__(self) -> None:
        self.received_context: str | None = None
        self.received_question: str | None = None

    def generate(self, question: str, context: str) -> str:
        self.received_question = question
        self.received_context = context
        if "capital of France" in context:
            return "According to the provided context, Paris is the capital of France."
        return INSUFFICIENT_CONTEXT_MESSAGE


class _InsufficientFakeGenerationClient:
    def generate(self, question: str, context: str) -> str:
        return INSUFFICIENT_CONTEXT_MESSAGE


class _PartialFakeGenerationClient:
    def generate(self, question: str, context: str) -> str:
        return (
            "The provided context states Paris is the capital of France. "
            "The context does not cover the city's population, so that "
            "part of the question is not answered here."
        )


class _FailingFakeGenerationClient:
    def generate(self, question: str, context: str) -> str:
        raise GenerationError("boom")


def _create_conversation(client, headers) -> str:
    resp = client.post("/conversations", headers=headers, json={})
    assert resp.status_code == 201
    return resp.json()["conversation"]["id"]


@pytest.fixture(autouse=True)
def _fake_embedding_client(monkeypatch):
    import app.services.embedding_client as embedding_client

    monkeypatch.setattr(embedding_client, "_default_client", _FakeEmbeddingClient())
    yield
    monkeypatch.setattr(embedding_client, "_default_client", None)


# ------------------------------------------------------------ AC-045/047 --


def test_grounded_answer_is_derived_only_from_retrieved_chunks(client):
    headers, user_id = _auth(client)
    _ready_document_with_chunk(user_id, PARIS_TEXT)
    conversation_id = _create_conversation(client, headers)

    fake = _GroundedFakeGenerationClient()
    set_generation_client(fake)

    resp = client.post(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
        json={"question": "What is the capital of France?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "Paris" in body["message"]["content"]
    assert len(body["citations"]) == 1
    assert body["citations"][0]["document_title_snapshot"] == "doc.txt"
    # The provider only ever saw the retrieved chunk text, never the raw
    # question treated as a source of facts on its own.
    assert PARIS_TEXT in fake.received_context
    assert UNRELATED_TEXT not in fake.received_context


# ------------------------------------------------------------ AC-046/049/050 --


def test_question_unanswered_by_retrieved_chunks_returns_exact_insufficient_message(client):
    headers, user_id = _auth(client, "noinfo@example.com")
    _ready_document_with_chunk(user_id, UNRELATED_TEXT)
    conversation_id = _create_conversation(client, headers)

    set_generation_client(_InsufficientFakeGenerationClient())

    resp = client.post(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
        json={"question": "What is the capital of Mongolia?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]["content"] == INSUFFICIENT_CONTEXT_MESSAGE
    assert body["citations"] == []


def test_insufficient_context_message_matches_ac_049_exactly():
    assert INSUFFICIENT_CONTEXT_MESSAGE == (
        "I don't have enough information in the provided context to answer that accurately."
    )


def test_empty_library_never_calls_generation_provider(client):
    headers, _ = _auth(client, "empty@example.com")
    conversation_id = _create_conversation(client, headers)

    set_generation_client(_FailingFakeGenerationClient())

    resp = client.post(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
        json={"question": "Anything?"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"]["content"] == EMPTY_LIBRARY_MESSAGE


# ------------------------------------------------------------------ AC-051 --


def test_partially_supported_question_answers_covered_part_and_flags_the_rest(client):
    headers, user_id = _auth(client, "partial@example.com")
    _ready_document_with_chunk(user_id, PARIS_TEXT)
    conversation_id = _create_conversation(client, headers)

    set_generation_client(_PartialFakeGenerationClient())

    resp = client.post(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
        json={"question": "What is the capital of France and what is its population?"},
    )
    assert resp.status_code == 200
    content = resp.json()["message"]["content"]
    assert "Paris is the capital of France" in content
    assert "does not cover" in content
    assert len(resp.json()["citations"]) == 1


# ------------------------------------------------------------------ AC-048 --


def test_provider_failure_returns_502_and_persists_no_assistant_message(client):
    headers, user_id = _auth(client, "failure@example.com")
    _ready_document_with_chunk(user_id, PARIS_TEXT)
    conversation_id = _create_conversation(client, headers)

    set_generation_client(_FailingFakeGenerationClient())

    resp = client.post(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
        json={"question": "What is the capital of France?"},
    )
    assert resp.status_code == 502
    assert "could not be generated" in resp.json()["detail"]

    detail = client.get(f"/conversations/{conversation_id}", headers=headers)
    messages = detail.json()["messages"]
    # The user's question is recorded, but no assistant message -- partial
    # or otherwise -- was ever persisted.
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
