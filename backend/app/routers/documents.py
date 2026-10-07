"""Document library CRUD and upload.

Every owned-resource lookup here must filter by the caller's id and return
404 on a mismatch, per the architecture note; `app.dependencies.get_owned_or_404`
is the single helper that does it.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import DOCUMENTS_CAP
from app.database import get_db
from app.dependencies import get_owned_or_404
from app.models import Document
from app.schemas import (
    DocumentCreateResponse,
    DocumentListResponse,
    DocumentOut,
    DocumentRenameRequest,
    RejectedFileOut,
)
from app.security import get_current_user_id
from app.services import storage
from app.services.document_service import (
    SUPPORTED_TYPES_MESSAGE,
    UnsupportedFileType,
    sniff_file_type,
)

router = APIRouter(prefix="/documents", tags=["documents"])

_CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
_DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=DocumentCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    user_id: _CurrentUserId,
    db: _DbSession,
    files: Annotated[list[UploadFile], File(...)],
) -> DocumentCreateResponse:
    """AC-014, AC-015, AC-016, AC-017: file upload only (no URL source);
    sniff each file's real content; one bad file in a multi-file upload does
    not block the others; enforce the single configurable document cap."""
    is_single = len(files) == 1
    sniffed: list[tuple[str, str, bytes]] = []
    rejected: list[RejectedFileOut] = []

    for upload in files:
        content = await upload.read()
        filename = upload.filename or "upload"
        try:
            file_type = sniff_file_type(filename, content)
        except UnsupportedFileType as exc:
            if is_single:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
                ) from exc
            rejected.append(RejectedFileOut(filename=filename, reason=str(exc)))
            continue
        sniffed.append((filename, file_type, content))

    if not sniffed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=SUPPORTED_TYPES_MESSAGE
        )

    current_count = db.query(Document).filter(Document.owner_id == user_id).count()
    if current_count + len(sniffed) > DOCUMENTS_CAP:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document cap of {DOCUMENTS_CAP} reached.",
        )

    created: list[Document] = []
    for filename, file_type, content in sniffed:
        doc = Document(
            owner_id=user_id,
            title=filename,
            file_type=file_type,
            storage_key="",
            status="processing",
        )
        db.add(doc)
        db.flush()
        doc.storage_key = storage.save_original(user_id, doc.id, filename, content)
        created.append(doc)

    db.commit()
    for doc in created:
        db.refresh(doc)

    return DocumentCreateResponse(
        documents=[DocumentOut.model_validate(doc) for doc in created],
        rejected=rejected,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(user_id: _CurrentUserId, db: _DbSession) -> DocumentListResponse:
    """AC-025, AC-027: only the caller's own documents, filtered by owner_id
    at the query level, not after serialisation."""
    docs = (
        db.query(Document)
        .filter(Document.owner_id == user_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return DocumentListResponse(documents=[DocumentOut.model_validate(doc) for doc in docs])


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID, user_id: _CurrentUserId, db: _DbSession
) -> DocumentOut:
    """AC-008: 404 if the caller does not own `document_id`."""
    doc = get_owned_or_404(db, Document, document_id, user_id, detail="document not found")
    return DocumentOut.model_validate(doc)


@router.patch("/{document_id}", response_model=DocumentOut)
async def rename_document(
    document_id: uuid.UUID,
    body: DocumentRenameRequest,
    user_id: _CurrentUserId,
    db: _DbSession,
) -> DocumentOut:
    """AC-028, AC-030, AC-008: reject an empty/whitespace title; 404 if the
    caller does not own `document_id`."""
    doc = get_owned_or_404(db, Document, document_id, user_id, detail="document not found")
    title = body.title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="title must not be empty",
        )
    doc.title = title
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return DocumentOut.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, user_id: _CurrentUserId, db: _DbSession) -> None:
    """AC-031, AC-008: delete the document, its original file and all
    chunks/vectors (cascade); 404 if the caller does not own `document_id`."""
    doc = get_owned_or_404(db, Document, document_id, user_id, detail="document not found")
    if doc.storage_key:
        storage.delete_original(doc.storage_key)
    db.delete(doc)
    db.commit()
