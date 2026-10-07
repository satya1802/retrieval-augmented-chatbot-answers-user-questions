"""The caller's own usage and fair-use standing (AC-013)."""

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import DOCUMENTS_CAP, MONTHLY_QUESTION_CAP
from app.database import get_db
from app.models import Document, User
from app.schemas import UsageResponse
from app.security import get_current_user_id

router = APIRouter(prefix="/me", tags=["me"])

_CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
_DbSession = Annotated[Session, Depends(get_db)]


@router.get("/usage", response_model=UsageResponse)
async def get_usage(user_id: _CurrentUserId, db: _DbSession) -> UsageResponse:
    """Documents stored, the document cap, and questions remaining in the
    current monthly window -- AC-013 and the document-cap requirement."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    document_count = db.query(Document).filter(Document.owner_id == user_id).count()
    remaining_questions = max(0, MONTHLY_QUESTION_CAP - user.monthly_question_count)
    reset_date = user.question_window_start + timedelta(days=30)

    return UsageResponse(
        document_count=document_count,
        documents_cap=DOCUMENTS_CAP,
        remaining_questions=remaining_questions,
        reset_date=reset_date,
    )
