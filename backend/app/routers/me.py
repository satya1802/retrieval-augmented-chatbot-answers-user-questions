"""The caller's own usage and fair-use standing (AC-013)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas import UsageResponse
from app.security import get_current_user_id

router = APIRouter(prefix="/me", tags=["me"])

_NOT_IMPLEMENTED = "Not implemented yet -- stub endpoint for the development sprint."


@router.get("/usage", response_model=UsageResponse)
async def get_usage(user_id: uuid.UUID = Depends(get_current_user_id)) -> UsageResponse:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
