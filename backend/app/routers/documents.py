"""Document library CRUD and upload.

Every owned-resource lookup here must filter by the caller's id and return
404 on a mismatch, per the architecture note -- that filtering is the
development sprint's job once a real query replaces the 501 below.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.schemas import (
    DocumentCreateResponse,
    DocumentListResponse,
    DocumentOut,
    DocumentRenameRequest,
)
from app.security import get_current_user_id

router = APIRouter(prefix="/documents", tags=["documents"])

_NOT_IMPLEMENTED = "Not implemented yet -- stub endpoint for the development sprint."

_CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]


@router.post("", response_model=DocumentCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(file: UploadFile, user_id: _CurrentUserId) -> DocumentCreateResponse:
    """AC-014, AC-015, AC-017, AC-011: enforce the document cap and supported
    file type, create a processing record and enqueue ingestion."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("", response_model=DocumentListResponse)
async def list_documents(user_id: _CurrentUserId) -> DocumentListResponse:
    """AC-025, AC-027: only the caller's own documents."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: uuid.UUID, user_id: _CurrentUserId) -> DocumentOut:
    """AC-008: 404 if the caller does not own `document_id`."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.patch("/{document_id}", response_model=DocumentOut)
async def rename_document(
    document_id: uuid.UUID,
    body: DocumentRenameRequest,
    user_id: _CurrentUserId,
) -> DocumentOut:
    """AC-028, AC-030: reject an empty/whitespace title."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, user_id: _CurrentUserId) -> None:
    """AC-031: delete the document, its original file and all chunks/vectors."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
