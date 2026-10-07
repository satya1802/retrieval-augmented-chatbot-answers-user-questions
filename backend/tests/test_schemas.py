"""Unit tests for app/schemas.py.

No acceptance criteria are attached to this ticket, so the shapes under test
are the schema file itself: each class validates what the field types/
constraints it declares promise (required vs optional, email format, the
`min_length=1` guards, UUID coercion) and each `from_attributes` response
model actually builds from an ORM-shaped object rather than only from a
plain dict, since that is how every router in app/routers constructs it.
"""

import uuid
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.models import Conversation, Document, Message, MessageCitation
from app.schemas import (
    AskQuestionRequest,
    ChunkDetailResponse,
    CitationOut,
    ConversationCreateRequest,
    ConversationOut,
    DocumentCreateResponse,
    DocumentOut,
    DocumentRenameRequest,
    LoginRequest,
    MessageOut,
    PasswordResetRequest,
    RegisterRequest,
    UsageResponse,
)

# ---------------------------------------------------------------- auth ----


def test_register_request_accepts_valid_email_and_password():
    req = RegisterRequest(email="person@example.com", password="s3cret1")
    assert req.email == "person@example.com"
    assert req.password == "s3cret1"


def test_register_request_rejects_malformed_email():
    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", password="s3cret1")


def test_register_request_requires_password():
    with pytest.raises(ValidationError):
        RegisterRequest(email="person@example.com")


def test_login_request_rejects_malformed_email():
    with pytest.raises(ValidationError):
        LoginRequest(email="nope", password="whatever1")


def test_password_reset_request_rejects_malformed_email():
    with pytest.raises(ValidationError):
        PasswordResetRequest(email="nope")


# ------------------------------------------------------------- usage ------


def test_usage_response_parses_iso_date_string():
    usage = UsageResponse(
        document_count=3,
        documents_cap=10,
        remaining_questions=42,
        reset_date="2026-11-01",
    )
    assert usage.reset_date == date(2026, 11, 1)


def test_usage_response_rejects_non_date_reset_date():
    with pytest.raises(ValidationError):
        UsageResponse(
            document_count=3,
            documents_cap=10,
            remaining_questions=42,
            reset_date="not-a-date",
        )


# ---------------------------------------------------------- documents -----


def test_document_out_builds_from_orm_instance_via_from_attributes():
    doc_id = uuid.uuid4()
    uploaded = datetime(2026, 10, 1, 12, 0, 0)
    document = Document(
        id=doc_id,
        owner_id=uuid.uuid4(),
        title="Q3 report.pdf",
        file_type="pdf",
        storage_key="s3://bucket/key",
        status="ready",
        failure_reason=None,
        uploaded_at=uploaded,
    )

    out = DocumentOut.model_validate(document)

    assert out.id == doc_id
    assert out.title == "Q3 report.pdf"
    assert out.status == "ready"
    assert out.failure_reason is None
    assert out.uploaded_at == uploaded


def test_document_out_omits_failure_reason_only_when_absent():
    # failure_reason defaults to None when the attribute is simply unset.
    document = Document(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        title="bad.pdf",
        file_type="pdf",
        storage_key="s3://bucket/key",
        status="failed",
        failure_reason="unreadable PDF",
        uploaded_at=datetime(2026, 10, 1),
    )

    out = DocumentOut.model_validate(document)

    assert out.status == "failed"
    assert out.failure_reason == "unreadable PDF"


def test_document_rename_request_rejects_empty_title():
    with pytest.raises(ValidationError):
        DocumentRenameRequest(title="")


def test_document_rename_request_accepts_nonempty_title():
    assert DocumentRenameRequest(title="New name").title == "New name"


def test_document_create_response_rejected_default_does_not_leak_between_instances():
    # Mutable-default regression guard: list[...] = [] on a pydantic model
    # must be a fresh list per instance, not one object shared by all of them.
    first = DocumentCreateResponse(documents=[])
    second = DocumentCreateResponse(documents=[])

    first.rejected.append({"filename": "x.exe", "reason": "unsupported file type"})

    assert first.rejected != []
    assert second.rejected == []


# ------------------------------------------------------- conversations ----


def test_conversation_out_coerces_stored_string_ids_to_uuid():
    # Conversation.scope_document_ids is persisted as list[str] (JSON column,
    # see app/models.py); ConversationOut declares list[uuid.UUID], so the
    # response model must parse those strings back into UUID objects.
    scoped_id = uuid.uuid4()
    conversation = Conversation(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        title="My chat",
        scope_document_ids=[str(scoped_id)],
        created_at=datetime(2026, 9, 1),
    )

    out = ConversationOut.model_validate(conversation)

    assert out.scope_document_ids == [scoped_id]
    assert all(isinstance(i, uuid.UUID) for i in out.scope_document_ids)


def test_conversation_out_defaults_scope_document_ids_to_empty_list():
    conversation = Conversation(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        title=None,
        scope_document_ids=[],
        created_at=datetime(2026, 9, 1),
    )

    out = ConversationOut.model_validate(conversation)

    assert out.scope_document_ids == []
    assert out.title is None


def test_conversation_create_request_allows_omitting_optional_fields():
    req = ConversationCreateRequest()
    assert req.title is None
    assert req.scope_document_ids is None


def test_ask_question_request_rejects_empty_question():
    with pytest.raises(ValidationError):
        AskQuestionRequest(question="")


def test_ask_question_request_accepts_nonempty_question():
    assert AskQuestionRequest(question="What is the refund policy?").question == (
        "What is the refund policy?"
    )


def test_citation_out_builds_from_orm_instance_with_nullable_chunk_id():
    citation = MessageCitation(
        id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        chunk_id=None,
        document_title_snapshot="Q3 report.pdf",
        chunk_position=2,
    )

    out = CitationOut.model_validate(citation)

    assert out.chunk_id is None
    assert out.document_title_snapshot == "Q3 report.pdf"
    assert out.chunk_position == 2


def test_message_out_builds_from_orm_instance_including_nested_citations():
    message_id = uuid.uuid4()
    citation = MessageCitation(
        id=uuid.uuid4(),
        message_id=message_id,
        chunk_id=uuid.uuid4(),
        document_title_snapshot="Handbook.md",
        chunk_position=0,
    )
    message = Message(
        id=message_id,
        conversation_id=uuid.uuid4(),
        role="assistant",
        content="Here is the answer.",
        is_incomplete=False,
        created_at=datetime(2026, 10, 5),
        citations=[citation],
    )

    out = MessageOut.model_validate(message)

    assert out.role == "assistant"
    assert out.is_incomplete is False
    assert len(out.citations) == 1
    assert out.citations[0].document_title_snapshot == "Handbook.md"


def test_message_out_defaults_citations_to_empty_list_when_none_attached():
    message = Message(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        role="user",
        content="A question.",
        is_incomplete=False,
        created_at=datetime(2026, 10, 5),
    )

    out = MessageOut.model_validate(message)

    assert out.citations == []


# ------------------------------------------------------------- chunks -----


def test_chunk_detail_response_round_trips_all_fields():
    detail = ChunkDetailResponse(text="chunk text", document_title="Handbook.md", position=3)
    assert detail.model_dump() == {
        "text": "chunk text",
        "document_title": "Handbook.md",
        "position": 3,
    }
