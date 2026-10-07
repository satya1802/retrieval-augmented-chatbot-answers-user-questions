"""Unit tests for app/models.py: the ORM layer itself, exercised directly
against a Session rather than through any router, so these fail whenever a
default, a cascade, a relationship ordering or the Embedding fallback stops
holding -- regardless of what the handlers built on top of them do.
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import JSON
from sqlalchemy.exc import IntegrityError

from app.database import Base, engine
from app.database import SessionLocal as _SessionLocal
from app.models import (
    AuthToken,
    Chunk,
    Conversation,
    Document,
    Embedding,
    Message,
    MessageCitation,
    User,
)

# Collection of this module alone (without app.main ever having been
# imported) would otherwise leave no tables to query against.
Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_state():
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


def _make_user(email: str) -> User:
    with _SessionLocal() as db:
        user = User(email=email, password_hash="hashed-value")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


# --------------------------------------------------------------- User -----


def test_user_defaults_are_applied_on_insert():
    with _SessionLocal() as db:
        user = User(email="defaults@example.com", password_hash="hashed-value")
        db.add(user)
        db.commit()
        db.refresh(user)

        assert isinstance(user.id, uuid.UUID)
        assert user.is_verified is False
        assert user.monthly_question_count == 0
        assert user.question_window_start == date.today()
        assert user.created_at is not None


def test_user_email_is_unique():
    _make_user("dup@example.com")
    with _SessionLocal() as db:
        db.add(User(email="dup@example.com", password_hash="other-hash"))
        with pytest.raises(IntegrityError):
            db.commit()


# ----------------------------------------------------------- AuthToken ----


def test_auth_token_records_purpose_and_starts_unused():
    user = _make_user("token@example.com")
    with _SessionLocal() as db:
        token = AuthToken(
            user_id=user.id,
            purpose="password_reset",
            token_hash="some-hash",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.add(token)
        db.commit()
        db.refresh(token)

        assert token.purpose == "password_reset"
        assert token.used_at is None

        token.used_at = datetime.utcnow()
        db.add(token)
        db.commit()
        db.refresh(token)
        assert token.used_at is not None


# ------------------------------------------------------------- Document ---


def test_document_defaults_to_processing_with_no_failure_reason():
    user = _make_user("docdefaults@example.com")
    with _SessionLocal() as db:
        doc = Document(owner_id=user.id, title="report.pdf", file_type="pdf", storage_key="k1")
        db.add(doc)
        db.commit()
        db.refresh(doc)

        assert doc.status == "processing"
        assert doc.failure_reason is None
        assert doc.uploaded_at is not None


# ------------------------------------------------------- Chunk / Embedding --


def test_chunk_embedding_round_trips_through_the_json_fallback_on_sqlite():
    user = _make_user("embed@example.com")
    with _SessionLocal() as db:
        doc = Document(owner_id=user.id, title="notes.txt", file_type="txt", storage_key="k2")
        db.add(doc)
        db.commit()
        db.refresh(doc)

        vector = [0.125, -0.5, 0.75]
        chunk = Chunk(document_id=doc.id, owner_id=user.id, position=0, text="hello", embedding=vector)
        db.add(chunk)
        db.commit()
        chunk_id = chunk.id

    with _SessionLocal() as db:
        reloaded = db.get(Chunk, chunk_id)
        assert reloaded.embedding == vector


def test_chunk_embedding_is_optional():
    user = _make_user("noembed@example.com")
    with _SessionLocal() as db:
        doc = Document(owner_id=user.id, title="pending.txt", file_type="txt", storage_key="k3")
        db.add(doc)
        db.commit()
        db.refresh(doc)

        chunk = Chunk(document_id=doc.id, owner_id=user.id, position=0, text="not embedded yet")
        db.add(chunk)
        db.commit()
        db.refresh(chunk)
        assert chunk.embedding is None


class _FakeDialect:
    """Stands in for a real `Dialect`: only `name` and `type_descriptor`
    are what `Embedding.load_dialect_impl` reads, and a real Postgres
    connection is exactly what this scaffold's SQLite default does not
    have."""

    def __init__(self, name: str) -> None:
        self.name = name

    def type_descriptor(self, type_):
        return type_


def test_embedding_falls_back_to_json_on_a_non_postgres_dialect():
    impl = Embedding().load_dialect_impl(_FakeDialect("sqlite"))
    assert isinstance(impl, JSON)


def test_embedding_uses_pgvector_on_a_postgres_dialect():
    from pgvector.sqlalchemy import Vector

    impl = Embedding().load_dialect_impl(_FakeDialect("postgresql"))
    assert isinstance(impl, Vector)


# --------------------------------------------------------- Conversation ---


def test_conversation_scope_document_ids_defaults_to_empty_list():
    user = _make_user("scope@example.com")
    with _SessionLocal() as db:
        convo = Conversation(owner_id=user.id)
        db.add(convo)
        db.commit()
        db.refresh(convo)
        assert convo.scope_document_ids == []


def test_conversation_messages_relationship_is_ordered_by_created_at_not_insertion():
    user = _make_user("order@example.com")
    with _SessionLocal() as db:
        convo = Conversation(owner_id=user.id)
        db.add(convo)
        db.commit()
        db.refresh(convo)
        convo_id = convo.id

    now = datetime.utcnow()
    with _SessionLocal() as db:
        later = Message(
            conversation_id=convo_id,
            role="user",
            content="later",
            created_at=now + timedelta(minutes=5),
        )
        db.add(later)
        db.commit()

    with _SessionLocal() as db:
        earlier = Message(conversation_id=convo_id, role="user", content="earlier", created_at=now)
        db.add(earlier)
        db.commit()

    with _SessionLocal() as db:
        reloaded = db.get(Conversation, convo_id)
        assert [m.content for m in reloaded.messages] == ["earlier", "later"]


# ----------------------------------------------------- MessageCitation ----


def test_message_citation_chunk_id_is_nullable_so_deleted_chunks_still_render():
    user = _make_user("citation@example.com")
    with _SessionLocal() as db:
        convo = Conversation(owner_id=user.id)
        db.add(convo)
        db.commit()
        db.refresh(convo)

        message = Message(conversation_id=convo.id, role="assistant", content="the answer")
        db.add(message)
        db.commit()
        db.refresh(message)

        citation = MessageCitation(
            message_id=message.id,
            chunk_id=None,
            document_title_snapshot="Since-Deleted Document",
            chunk_position=3,
        )
        db.add(citation)
        db.commit()
        db.refresh(citation)

        assert citation.chunk_id is None
        assert citation.document_title_snapshot == "Since-Deleted Document"
        assert citation.chunk_position == 3


# ------------------------------------------------------- cascade deletes --


def test_deleting_a_user_cascades_through_every_owned_table():
    """A `User` is declared with `cascade="all, delete-orphan"` on
    auth_tokens, documents and conversations, and each of those cascades
    again (Document -> Chunk, Conversation -> Message -> MessageCitation).
    Deleting the user should leave nothing behind in any of the six tables
    -- the whole point of modelling the relationships this way rather than
    leaving cleanup to be remembered elsewhere."""
    user = _make_user("cascade@example.com")

    with _SessionLocal() as db:
        doc = Document(owner_id=user.id, title="t", file_type="pdf", storage_key="k")
        token = AuthToken(
            user_id=user.id,
            purpose="verify",
            token_hash="h",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        convo = Conversation(owner_id=user.id)
        db.add_all([doc, token, convo])
        db.commit()
        db.refresh(doc)
        db.refresh(convo)

        chunk = Chunk(document_id=doc.id, owner_id=user.id, position=0, text="hello")
        db.add(chunk)
        message = Message(conversation_id=convo.id, role="user", content="hi")
        db.add(message)
        db.commit()
        db.refresh(chunk)
        db.refresh(message)

        citation = MessageCitation(
            message_id=message.id,
            chunk_id=chunk.id,
            document_title_snapshot="t",
            chunk_position=0,
        )
        db.add(citation)
        db.commit()

        user_id = user.id

    with _SessionLocal() as db:
        db.delete(db.get(User, user_id))
        db.commit()

    with _SessionLocal() as db:
        assert db.query(User).filter_by(id=user_id).count() == 0
        assert db.query(Document).filter_by(owner_id=user_id).count() == 0
        assert db.query(AuthToken).filter_by(user_id=user_id).count() == 0
        assert db.query(Conversation).filter_by(owner_id=user_id).count() == 0
        assert db.query(Chunk).filter_by(owner_id=user_id).count() == 0
        assert db.query(Message).count() == 0
        assert db.query(MessageCitation).count() == 0
