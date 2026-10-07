"""Chunk lookup for citation inspection (AC-071, AC-072, AC-034)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_or_404
from app.models import Chunk
from app.schemas import ChunkDetailResponse
from app.security import get_current_user_id

router = APIRouter(prefix="/chunks", tags=["chunks"])

_CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
_DbSession = Annotated[Session, Depends(get_db)]

# AC-034: one message for "never existed", "not yours" and "its document was
# deleted" (a document delete cascades the chunk row away entirely, so by
# the time this lookup runs there is no way -- and no need -- to tell that
# case apart from an unknown id). Never leaks existence, never returns text.
_NOT_FOUND_DETAIL = "source document is no longer available"


@router.get("/{chunk_id}", response_model=ChunkDetailResponse)
async def get_chunk(
    chunk_id: uuid.UUID, user_id: _CurrentUserId, db: _DbSession
) -> ChunkDetailResponse:
    """404 -- with the exact `_NOT_FOUND_DETAIL` body -- for an unowned,
    unknown, or deleted-document chunk alike (AC-008, AC-034).

    `Chunk.owner_id` is denormalized onto the row precisely so this lookup
    filters by owner at the query level without a join.
    """
    chunk = get_owned_or_404(db, Chunk, chunk_id, user_id, detail=_NOT_FOUND_DETAIL)
    return ChunkDetailResponse(
        text=chunk.text,
        document_title=chunk.document.title,
        position=chunk.position,
    )
