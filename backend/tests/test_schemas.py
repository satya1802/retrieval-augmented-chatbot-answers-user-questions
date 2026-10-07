"""Unit tests for backend/app/schemas.py.

These exercise the Pydantic shapes directly -- validation rules, defaults,
and the `from_attributes` ORM mapping each `*Out` schema relies on when a
router does `Schema.model_validate(some_model_instance)` -- rather than
through an endpoint, since the schemas carry no endpoint of their own.
"""

import uuid
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.schemas import (
    AskQuestionRequest,
    AskQuestionResponse,
    ChunkDetailResponse,
    CitationOut,
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationOut,
    DocumentCreateResponse,
    DocumentListResponse,
    DocumentOut,
    DocumentRenameRequest,
    LoginRequest,
    LoginResponse,
    MessageOut,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    RejectedFileOut,
    UsageResponse,
    VerifyRequest,
    VerifyResponse,
)


# --------------------------------------------------------------- auth -----


def test_register_request_accepts_valid_email_and_password():
    req = RegisterRequest(email="user@example.com", password="s3cret")
    assert req.email == "user@example.com"
    assert req.password == "s3cret"


def test_register_request_rejects_malformed_email():
    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", password="s3cret")


def test_login_response_requires_access_token():
    with pytest.raises(ValidationError):
        LoginResponse()
    assert LoginResponse(access_token="jwt.token.value").access_token == "jwt.token.value"


def test_verify_response_coerces_but_requires_verified_field():
    with pytest.raises(ValidationError):
        VerifyResponse()
    assert VerifyResponse(verified=True).verified is True


def test_password_reset_request_validates_email_shape():
    with pytest.raises(ValidationError):
        PasswordResetRequest(email="nope")
    assert PasswordResetRequest(email="a@b.com").email == "a@b.com"


def test_password_reset_confirm_request_requires_both_fields():
    with pytest.raises(ValidationError):
        PasswordResetConfirmRequest(token="abc")
    confirm = PasswordResetConfirmRequest(token="abc", new_password="newpass")
    assert confirm.token == "abc"
    assert confirm.new_password == "newpass"


def test_verify_request_requires_token():
    with pytest.raises(ValidationError):
        VerifyRequest()
    assert VerifyRequest(token="tok").token == "tok"


def test_message_response_wraps_a_plain_string():
    assert MessageResponse(message="ok").message == "ok"


# -------------------------------------------------------------- usage -----


def test_usage_response_requires_all_fields():
    with pytest.raises(ValidationError):
        UsageResponse(document_count=1, documents_cap=10, remaining_questions=5)
    usage = UsageResponse(
        document_count=1,
        documents_cap=10,
        remaining_questions=5,
        reset_date=date(2026, 11, 1),
    )
    assert usage.reset_date == date(2026, 11, 1)


# ----------------------------------------------------------- documents ----


class _FakeDocument:
    """Stands in for app.models.Document: attribute access only, no dict()."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_document_out_builds_from_orm_attributes():
    model = _FakeDocument(
        id=uuid.uuid4(),
        title="Q3 report.pdf",
        file_type="pdf",
        status="ready",
        failure_reason=None,
        uploaded_at=datetime(2026, 10, 1, 12, 0, 0),
    )
    out = DocumentOut.model_validate(model)
    assert out.title == "Q3 report.pdf"
    assert out.status == "ready"
    assert out.failure_reason is None


def test_document_out_carries_failure_reason_when_set():
    model = _FakeDocument(
        id=uuid.uuid4(),
        title="bad.exe",
        file_type="exe",
        status="failed",
        failure_reason="unsupported file type",
        uploaded_at=datetime(2026, 10, 1, 12, 0, 0),
    )
    out = DocumentOut.model_validate(model)
    assert out.status == "failed"
    assert out.failure_reason == "unsupported file type"


def test_document_create_response_defaults_rejected_to_empty_list():
    model = _FakeDocument(
        id=uuid.uuid4(),
        title="notes.md",
        file_type="md",
        status="processing",
        failure_reason=None,
        uploaded_at=datetime(2026, 10, 1, 12, 0, 0),
    )
    response = DocumentCreateResponse(documents=[DocumentOut.model_validate(model)])
    assert response.rejected == []


def test_document_create_response_carries_rejected_files_with_reason():
    response = DocumentCreateResponse(
        documents=[],
        rejected=[RejectedFileOut(filename="virus.exe", reason="unsupported file type")],
    )
    assert len(response.rejected) == 1
    assert response.rejected[0].filename == "virus.exe"
    assert response.rejected[0].reason == "unsupported file type"


def test_document_list_response_holds_multiple_documents():
    models = [
        _FakeDocument(
            id=uuid.uuid4(),
            title=f"doc-{i}.pdf",
            file_type="pdf",
            status="ready",
            failure_reason=None,
            uploaded_at=datetime(2026, 10, 1, 12, 0, 0),
        )
        for i in range(2)
    ]
    response = DocumentListResponse(documents=[DocumentOut.model_validate(m) for m in models])
    assert len(response.documents) == 2


def test_document_rename_request_rejects_empty_title():
    with pytest.raises(ValidationError):
        DocumentRenameRequest(title="")


def test_document_rename_request_rejects_title_over_300_chars():
    # Matches `documents.title varchar(300)` -- a title past the bound must
    # fail here, in the schema, rather than reach a database that enforces
    # it only on Postgres (SQLite does not).
    with pytest.raises(ValidationError):
        DocumentRenameRequest(title="x" * 301)


def test_document_rename_request_accepts_title_at_300_chars():
    assert DocumentRenameRequest(title="x" * 300).title == "x" * 300


# ------------------------------------------------------- conversations ----


def test_conversation_out_defaults_title_and_scope_when_absent():
    model = _FakeDocument(
        id=uuid.uuid4(),
        title=None,
        scope_document_ids=[],
        created_at=datetime(2026, 10, 1, 12, 0, 0),
    )
    out = ConversationOut.model_validate(model)
    assert out.title is None
    assert out.scope_document_ids == []


def test_conversation_create_request_defaults_are_none():
    req = ConversationCreateRequest()
    assert req.title is None
    assert req.scope_document_ids is None


def test_conversation_create_request_rejects_title_over_300_chars():
    with pytest.raises(ValidationError):
        ConversationCreateRequest(title="x" * 301)


def test_conversation_create_request_rejects_malformed_scope_document_id():
    with pytest.raises(ValidationError):
        ConversationCreateRequest(scope_document_ids=["not-a-uuid"])


def test_conversation_create_response_wraps_conversation_out():
    convo = ConversationOut(
        id=uuid.uuid4(), title="My chat", scope_document_ids=[], created_at=datetime.utcnow()
    )
    response = ConversationCreateResponse(conversation=convo)
    assert response.conversation.title == "My chat"


def test_conversation_list_response_holds_many_conversations():
    convo = ConversationOut(
        id=uuid.uuid4(), title=None, scope_document_ids=[], created_at=datetime.utcnow()
    )
    response = ConversationListResponse(conversations=[convo, convo])
    assert len(response.conversations) == 2


def test_citation_out_allows_null_chunk_id_for_deleted_chunk():
    # MessageCitation.chunk_id is nullable with ON DELETE SET NULL precisely
    # so a citation still renders after its chunk is gone; the schema must
    # not force that field to be present.
    citation = CitationOut(
        chunk_id=None, document_title_snapshot="Deleted doc.pdf", chunk_position=3
    )
    assert citation.chunk_id is None
    assert citation.document_title_snapshot == "Deleted doc.pdf"


def test_message_out_defaults_citations_to_empty_list():
    message = MessageOut(
        id=uuid.uuid4(),
        role="assistant",
        content="hello",
        is_incomplete=False,
        created_at=datetime.utcnow(),
    )
    assert message.citations == []


def test_message_out_builds_from_orm_attributes_with_citations():
    fake_message = _FakeDocument(
        id=uuid.uuid4(),
        role="assistant",
        content="The answer is 42.",
        is_incomplete=False,
        created_at=datetime(2026, 10, 1, 12, 0, 0),
        citations=[
            _FakeDocument(
                chunk_id=uuid.uuid4(), document_title_snapshot="Guide.pdf", chunk_position=1
            )
        ],
    )
    out = MessageOut.model_validate(fake_message)
    assert out.content == "The answer is 42."
    assert len(out.citations) == 1
    assert out.citations[0].document_title_snapshot == "Guide.pdf"


def test_conversation_detail_response_bundles_conversation_and_messages():
    convo = ConversationOut(
        id=uuid.uuid4(), title=None, scope_document_ids=[], created_at=datetime.utcnow()
    )
    message = MessageOut(
        id=uuid.uuid4(),
        role="user",
        content="hi",
        is_incomplete=False,
        created_at=datetime.utcnow(),
    )
    detail = ConversationDetailResponse(conversation=convo, messages=[message])
    assert detail.messages[0].role == "user"


def test_ask_question_request_rejects_empty_question():
    with pytest.raises(ValidationError):
        AskQuestionRequest(question="")


def test_ask_question_request_accepts_nonempty_question():
    assert AskQuestionRequest(question="What is the refund policy?").question == (
        "What is the refund policy?"
    )


def test_ask_question_response_pairs_message_and_citations():
    message = MessageOut(
        id=uuid.uuid4(),
        role="assistant",
        content="Per the policy...",
        is_incomplete=False,
        created_at=datetime.utcnow(),
    )
    citation = CitationOut(
        chunk_id=uuid.uuid4(), document_title_snapshot="Policy.pdf", chunk_position=0
    )
    response = AskQuestionResponse(message=message, citations=[citation])
    assert response.citations[0].document_title_snapshot == "Policy.pdf"


def test_message_out_is_incomplete_flags_a_truncated_answer():
    message = MessageOut(
        id=uuid.uuid4(),
        role="assistant",
        content="The answer got cut off because",
        is_incomplete=True,
        created_at=datetime.utcnow(),
    )
    assert message.is_incomplete is True


# ----------------------------------------------------------- chunks -----


def test_chunk_detail_response_requires_all_three_fields():
    with pytest.raises(ValidationError):
        ChunkDetailResponse(text="some text", document_title="doc.pdf")
    detail = ChunkDetailResponse(text="some text", document_title="doc.pdf", position=2)
    assert detail.position == 2
