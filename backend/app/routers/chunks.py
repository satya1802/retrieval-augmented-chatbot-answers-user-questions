"""Chunk lookup for citation inspection (AC-071, AC-072, AC-034)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas import ChunkDetailResponse
from app.security import get_current_user_id

router = APIRouter(prefix="/chunks", tags=["chunks"])

_NOT_IMPLEMENTED = "Not implemented yet -- stub endpoint for the development sprint."


@router.get("/{chunk_id}", response_model=ChunkDetailResponse)
async def get_chunk(
    chunk_id: uuid.UUID, user_id: uuid.UUID = Depends(get_current_user_id)
) -> ChunkDetailResponse:
    """404 if the caller does not own the chunk's document."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
