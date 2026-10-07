"""Conversations and the question-asking endpoint.

`POST /conversations` accepts an optional `scope_document_ids`, validated at
creation time against the caller's own *ready* documents (AC-039): an id
that is not owned, or not yet ready, is rejected with 422 rather than
silently dropped or silently accepted. `POST /{id}/messages` retrieves
context chunks via `retrieve_context` -- scoped to that conversation, or
with no scope set, to all of the caller's ready documents (AC-040) -- and
passes only those chunks to the hosted generation provider (US-014-1): a
grounded response with citations, the exact insufficient-context string, or
a 502 error when the provider itself fails. It never invents an answer and
never falls back to documents outside the scope.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import MONTHLY_QUESTION_CAP
from app.database import get_db
from app.dependencies import get_owned_or_404
from app.models import Conversation, Document, Message, MessageCitation, User
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
from app.services.generation_client import GenerationError, get_generation_client
from app.services.retrieval import READY_STATUS, ContextChunk, retrieve_context

router = APIRouter(prefix="/conversations", tags=["conversations"])

_CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
_DbSession = Annotated[Session, Depends(get_db)]

# AC-049: the exact string the Answer section must contain -- and nothing
# else -- whenever the retrieved (or generated-from) context is inadequate
# to answer the question, whether that is because retrieval found nothing
# at all or because the provider itself determined the retrieved chunks
# don't support an answer. Replaces the earlier, non-conforming wording.
INSUFFICIENT_CONTEXT_MESSAGE = (
    "I don't have enough information in the provided context to answer that accurately."
)
EMPTY_LIBRARY_MESSAGE = (
    "Your document library is empty or still processing. "
    "Upload a document -- or wait for it to finish processing -- before asking a question."
)
# AC-048: the 502 surfaced when the hosted provider call fails or times
# out -- never a fabricated answer and never a partial, unmarked one.
_GENERATION_FAILURE_DETAIL = (
    "The answer could not be generated because the AI provider failed. Please try again."
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


def _build_context_text(chunks: list[ContextChunk]) -> str:
    """The only content passed to the generation provider besides the
    system prompt (AC-045) -- each retrieved chunk, numbered and
    attributed to its source document, so the model's answer can be
    checked against exactly these passages and nothing else."""
    sections = [
        f'[{idx}] (from "{chunk.document_title}"): {chunk.text}'
        for idx, chunk in enumerate(chunks, start=1)
    ]
    return "\n\n".join(sections)


@router.post("/{conversation_id}/messages", response_model=AskQuestionResponse)
async def ask_question(
    conversation_id: uuid.UUID,
    body: AskQuestionRequest,
    user_id: _CurrentUserId,
    db: _DbSession,
) -> AskQuestionResponse:
    """AC-039, AC-040, AC-041, AC-038, AC-032, AC-012, AC-009, AC-045
    through AC-051: ownership and the monthly question cap are both
    enforced before anything else runs, including before any
    embedding/retrieval/generation call (AC-012). Retrieval is then scoped
    to exactly `conversation.scope_document_ids` when a scope is set
    (AC-039) -- so chunks from an unselected document are never in the
    context set -- or to all of the caller's ready documents when no scope
    is set (AC-040).

    A caller with no ready documents at all in the relevant scope never
    reaches retrieval -- let alone an embedding or generation provider call
    -- and instead gets a response stating the library is empty or still
    processing (AC-038). When retrieval returns chunks, those chunks --
    and only those chunks -- are passed to the hosted generation provider
    (AC-045); its answer is used verbatim unless it is exactly the
    insufficient-context sentence, in which case no citations are attached
    (AC-050). The assistant message and its citations are only persisted
    after a successful generation call: a provider failure or timeout
    raises a 502 instead, with no assistant message, partial or otherwise,
    stored (AC-048).
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
    db.commit()

    citation_chunks: list[ContextChunk] = []
    if not has_ready_documents:
        content = EMPTY_LIBRARY_MESSAGE
    else:
        retrieved = retrieve_context(db, user_id, body.question, document_ids=scope_ids)
        if not retrieved:
            content = INSUFFICIENT_CONTEXT_MESSAGE
        else:
            context_text = _build_context_text(retrieved)
            try:
                content = get_generation_client().generate(body.question, context_text)
            except GenerationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=_GENERATION_FAILURE_DETAIL,
                ) from exc
            # AC-050: no sources attached to a response the provider itself
            # judged unsupported by the retrieved context.
            if content.strip() != INSUFFICIENT_CONTEXT_MESSAGE:
                citation_chunks = retrieved

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
            chunk_id=chunk.chunk_id,
            document_title_snapshot=chunk.document_title,
            chunk_position=chunk.position,
        )
        for chunk in citation_chunks
    ]
    db.add_all(citation_rows)
    db.commit()
    db.refresh(assistant_message)

    return AskQuestionResponse(
        message=MessageOut.model_validate(assistant_message),
        citations=[CitationOut.model_validate(c) for c in citation_rows],
    )
