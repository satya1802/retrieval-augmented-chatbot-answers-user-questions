"""Conversations and the question-asking endpoint.

`POST /conversations` accepts an optional `scope_document_ids`, validated at
creation time against the caller's own *ready* documents (AC-039): an id
that is not owned, or not yet ready, is rejected with 422 rather than
silently dropped or silently accepted. `POST /{id}/messages` retrieves
context chunks scoped to that conversation -- or, with no scope set, to all
of the caller's ready documents (AC-040) -- and answers either a grounded
response with citations or the exact insufficient-context string, never
inventing an answer and never falling back to documents outside the scope.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import MONTHLY_QUESTION_CAP
from app.database import get_db
from app.dependencies import get_owned_or_404
from app.models import Chunk, Conversation, Document, Message, MessageCitation, User
from app.schemas import (
    AskQuestionRequest,
    AskQuestionResponse,
    CitationOut,
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationOut,
    MessageOut,
)
from app.security import get_current_user_id
from app.services import usage_service
from app.services.retrieval import READY_STATUS, build_context_chunk_query

router = APIRouter(prefix="/conversations", tags=["conversations"])

_CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
_DbSession = Annotated[Session, Depends(get_db)]

# AC-041, AC-038: exactly one string for "retrieval ran but found nothing to
# answer from", kept here as the single shared constant rather than
# duplicated at each place the response is built, and a distinct string for
# "there was nothing to retrieve from in the first place" so the two never
# get confused with one another or with an invented answer.
INSUFFICIENT_CONTEXT_MESSAGE = (
    "I don't have enough information in the selected documents to answer that question."
)
EMPTY_LIBRARY_MESSAGE = (
    "Your document library is empty or still processing. "
    "Upload a document -- or wait for it to finish processing -- before asking a question."
)

_SCOPE_VALIDATION_DETAIL = "scope_document_ids must reference the caller's own ready documents"


@router.get("", response_model=ConversationListResponse)
async def list_conversations(user_id: _CurrentUserId, db: _DbSession) -> ConversationListResponse:
    """AC-073, AC-075: only the caller's own conversations, filtered by
    owner_id at the query level, not after serialisation."""
    conversations = (
        db.query(Conversation)
        .filter(Conversation.owner_id == user_id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return ConversationListResponse(
        conversations=[ConversationOut.model_validate(c) for c in conversations]
    )


@router.post("", response_model=ConversationCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreateRequest, user_id: _CurrentUserId, db: _DbSession
) -> ConversationCreateResponse:
    """AC-039, AC-076: an optional document scope at creation time, which
    must be the caller's own, ready documents -- anything else (unowned,
    unknown, or still processing/failed) is rejected with 422 rather than
    silently stored or silently dropped, since a scope that silently
    narrowed to less than the caller asked for would be worse than an
    error."""
    if body.scope_document_ids:
        requested_ids = list(dict.fromkeys(body.scope_document_ids))  # de-dup, preserve order
        owned_ready = (
            db.query(Document)
            .filter(Document.id.in_(requested_ids), Document.owner_id == user_id)
            .all()
        )
        owned_ready_by_id = {doc.id: doc for doc in owned_ready}
        for doc_id in requested_ids:
            doc = owned_ready_by_id.get(doc_id)
            if doc is None or doc.status != READY_STATUS:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=_SCOPE_VALIDATION_DETAIL,
                )
        scope_ids = [str(doc_id) for doc_id in requested_ids]
    else:
        scope_ids = []

    conversation = Conversation(owner_id=user_id, title=body.title, scope_document_ids=scope_ids)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationCreateResponse(conversation=ConversationOut.model_validate(conversation))


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID, user_id: _CurrentUserId, db: _DbSession
) -> ConversationDetailResponse:
    """AC-073, AC-008: owned conversation with its messages; 404 on a
    mismatch via the single owner-scoped lookup helper."""
    conversation = get_owned_or_404(
        db, Conversation, conversation_id, user_id, detail="conversation not found"
    )
    messages = [MessageOut.model_validate(message) for message in conversation.messages]
    return ConversationDetailResponse(
        conversation=ConversationOut.model_validate(conversation), messages=messages
    )


def _compose_answer(chunk_count: int) -> str:
    """A minimal, deterministic grounded response. Real synthesis over the
    retrieved chunks is a later ticket's generation pipeline; this one is
    scoped to retrieval and conversation scoping, so the message only
    states that sources were found -- it never states anything the chunks
    themselves don't support."""
    plural = "s" if chunk_count != 1 else ""
    return f"Found {chunk_count} relevant passage{plural} in your documents."


@router.post("/{conversation_id}/messages", response_model=AskQuestionResponse)
async def ask_question(
    conversation_id: uuid.UUID,
    body: AskQuestionRequest,
    user_id: _CurrentUserId,
    db: _DbSession,
) -> AskQuestionResponse:
    """AC-039, AC-040, AC-041, AC-038, AC-032, AC-012, AC-009: ownership and
    the monthly question cap are both enforced before anything else runs,
    including before any embedding/retrieval call (AC-012). Retrieval is
    then scoped to exactly `conversation.scope_document_ids` when a scope is
    set (AC-039) -- so chunks from an unselected document are never in the
    context set, and a scoped conversation whose documents don't cover the
    question gets the exact insufficient-context response rather than a
    fallback to the rest of the library (AC-041) -- or to all of the
    caller's ready documents when no scope is set (AC-040).

    A caller with no ready documents at all in the relevant scope never
    reaches the retrieval query -- let alone an embedding provider call --
    and instead gets a response stating the library is empty or still
    processing (AC-038). A deleted document's chunks cannot appear here
    either way: `build_context_chunk_query` filters on `Document.status ==
    'ready'`, and a deleted document's chunk rows are gone entirely
    (AC-032).
    """
    conversation = get_owned_or_404(
        db, Conversation, conversation_id, user_id, detail="conversation not found"
    )

    user = db.get(User, user_id)
    usage_service.enforce_question_capacity(db, user, cap=MONTHLY_QUESTION_CAP)

    scope_ids = (
        [uuid.UUID(doc_id) for doc_id in conversation.scope_document_ids]
        if conversation.scope_document_ids
        else None
    )

    ready_documents_query = db.query(Document).filter(
        Document.owner_id == user_id, Document.status == READY_STATUS
    )
    if scope_ids:
        ready_documents_query = ready_documents_query.filter(Document.id.in_(scope_ids))
    has_ready_documents = db.query(ready_documents_query.exists()).scalar()

    usage_service.increment_question_count(db, user)

    user_message = Message(conversation_id=conversation.id, role="user", content=body.question)
    db.add(user_message)

    chunks: list[Chunk] = []
    if not has_ready_documents:
        content = EMPTY_LIBRARY_MESSAGE
    else:
        chunks = build_context_chunk_query(db, user_id, document_ids=scope_ids).all()
        content = _compose_answer(len(chunks)) if chunks else INSUFFICIENT_CONTEXT_MESSAGE

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        is_incomplete=False,
    )
    db.add(assistant_message)
    db.flush()

    citation_rows = [
        MessageCitation(
            message_id=assistant_message.id,
            chunk_id=chunk.id,
            document_title_snapshot=chunk.document.title,
            chunk_position=chunk.position,
        )
        for chunk in chunks
    ]
    db.add_all(citation_rows)
    db.commit()
    db.refresh(assistant_message)

    return AskQuestionResponse(
        message=MessageOut.model_validate(assistant_message),
        citations=[CitationOut.model_validate(c) for c in citation_rows],
    )
