"""Conversations and the question-asking endpoint.

`POST /{id}/messages` is specified as a streamed `text/event-stream` response
(tokens, then a final `{message, citations}` payload) once retrieval and
generation exist. A stub has nothing to stream, so it answers the same 501
every other handler in this file does; the route, its auth and its request
schema are already correct for the handler that replaces this body.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas import (
    AskQuestionRequest,
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationDetailResponse,
    ConversationListResponse,
)
from app.security import get_current_user_id

router = APIRouter(prefix="/conversations", tags=["conversations"])

_NOT_IMPLEMENTED = "Not implemented yet -- stub endpoint for the development sprint."


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ConversationListResponse:
    """AC-073, AC-075: only the caller's own conversations."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("", response_model=ConversationCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreateRequest, user_id: uuid.UUID = Depends(get_current_user_id)
) -> ConversationCreateResponse:
    """AC-039, AC-076: optional document scope at creation time."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID, user_id: uuid.UUID = Depends(get_current_user_id)
) -> ConversationDetailResponse:
    """AC-073: owned conversation with its messages, answers and citations."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/{conversation_id}/messages")
async def ask_question(
    conversation_id: uuid.UUID,
    body: AskQuestionRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """AC-035, AC-049, AC-052, AC-067, AC-068, AC-069, AC-012: enforce the
    question cap, reject empty questions, rewrite follow-ups, retrieve top-k
    chunks and stream a grounded Answer/Sources or the exact
    insufficient-context string."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
