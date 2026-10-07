"""Conversations and the question-asking endpoint.

`POST /{id}/messages` is specified as a streamed `text/event-stream` response
(tokens, then a final `{message, citations}` payload) once retrieval and
generation exist. That pipeline is not built this sprint, but the handler
still verifies ownership of the conversation and constructs the owner-scoped
chunk-retrieval query (AC-009) before answering the same 501 every other stub
in this file does -- the route, its auth, its ownership check and its
request schema are already correct for the handler that replaces this body.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_or_404
from app.models import Conversation
from app.schemas import (
    AskQuestionRequest,
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationOut,
    MessageOut,
)
from app.security import get_current_user_id
from app.services.retrieval import build_context_chunk_query

router = APIRouter(prefix="/conversations", tags=["conversations"])

_NOT_IMPLEMENTED = "Not implemented yet -- stub endpoint for the development sprint."

_CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
_DbSession = Annotated[Session, Depends(get_db)]


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
    """AC-039, AC-076: optional document scope at creation time."""
    scope_ids = (
        [str(doc_id) for doc_id in body.scope_document_ids] if body.scope_document_ids else []
    )
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


@router.post("/{conversation_id}/messages")
async def ask_question(
    conversation_id: uuid.UUID,
    body: AskQuestionRequest,
    user_id: _CurrentUserId,
    db: _DbSession,
):
    """AC-035, AC-049, AC-052, AC-067, AC-068, AC-069, AC-012, AC-009:
    enforce the question cap, reject empty questions, rewrite follow-ups,
    retrieve top-k chunks scoped to the caller and stream a grounded
    Answer/Sources or the exact insufficient-context string.

    Ownership of the conversation is checked first, and the context-chunk
    query is built with the same owner_id predicate the retrieval pipeline
    will use once it exists, so later work inherits the isolation rather
    than having to add it."""
    conversation = get_owned_or_404(
        db, Conversation, conversation_id, user_id, detail="conversation not found"
    )
    document_ids = (
        [uuid.UUID(doc_id) for doc_id in conversation.scope_document_ids]
        if conversation.scope_document_ids
        else None
    )
    build_context_chunk_query(db, user_id, document_ids=document_ids)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
