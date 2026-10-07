"""The caller's own usage and fair-use standing (AC-013)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import DOCUMENTS_CAP, MONTHLY_QUESTION_CAP
from app.database import get_db
from app.models import Document, User
from app.schemas import UsageResponse
from app.security import get_current_user_id
from app.services import usage_service

router = APIRouter(prefix="/me", tags=["me"])

_CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
_DbSession = Annotated[Session, Depends(get_db)]


@router.get("/usage", response_model=UsageResponse)
async def get_usage(user_id: _CurrentUserId, db: _DbSession) -> UsageResponse:
    """Documents stored, the document cap, and questions remaining in the
    current monthly window -- for the authenticated caller only (AC-013)."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    # Mirrors the rollover `enforce_question_capacity` performs before a
    # question is asked, so a usage check between two questions never
    # reports a stale count from an already-elapsed window, nor a
    # reset_date that has already passed.
    usage_service.ensure_question_window_current(db, user)

    document_count = db.query(Document).filter(Document.owner_id == user_id).count()
    remaining_questions = max(0, MONTHLY_QUESTION_CAP - user.monthly_question_count)
    reset_date = usage_service.question_reset_date(user)

    return UsageResponse(
        document_count=document_count,
        documents_cap=DOCUMENTS_CAP,
        remaining_questions=remaining_questions,
        reset_date=reset_date,
    )
