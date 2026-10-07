"""Document library CRUD and upload.

Every owned-resource lookup here must filter by the caller's id and return
404 on a mismatch, per the architecture note; `app.dependencies.get_owned_or_404`
is the single helper that does it.
"""

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.config import DOCUMENTS_CAP
from app.database import get_db
from app.dependencies import get_owned_or_404
from app.models import Chunk, Document, MessageCitation
from app.schemas import (
    DocumentCreateResponse,
    DocumentListResponse,
    DocumentOut,
    DocumentRenameRequest,
    RejectedFileOut,
)
from app.security import get_current_user_id
from app.services import storage, usage_service
from app.services.document_service import (
    SUPPORTED_TYPES_MESSAGE,
    UnsupportedFileType,
    sniff_file_type,
)
from app.services.ingestion_service import run_ingestion

router = APIRouter(prefix="/documents", tags=["documents"])

_CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
_DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=DocumentCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    user_id: _CurrentUserId,
    db: _DbSession,
    background_tasks: BackgroundTasks,
    files: Annotated[list[UploadFile], File(...)],
) -> DocumentCreateResponse:
    """AC-014, AC-015, AC-016, AC-017: file upload only (no URL source);
    sniff each file's real content; one bad file in a multi-file upload does
    not block the others; enforce the single configurable document cap
    (AC-011), via app.services.usage_service so the cap arithmetic lives in
    one place shared with the question-cap check. `DOCUMENTS_CAP` is passed
    in explicitly (rather than read inside the service) so this module's
    own constant remains the one a test or future per-request override
    would patch.

    AC-018, AC-021: each accepted file is enqueued for out-of-request
    ingestion (extract, chunk, embed, persist) so the response returns 202
    immediately and the client never holds the connection open while that
    runs.
    """
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

    usage_service.check_document_capacity(db, user_id, additional=len(sniffed), cap=DOCUMENTS_CAP)

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
        background_tasks.add_task(run_ingestion, doc.id)

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
    """AC-031, AC-008, AC-032, AC-034: delete the document, its stored
    original and every chunk (text and embedding) belonging to it, so a
    post-delete query for that document_id's chunks returns zero rows and
    retrieval can never surface them again.

    Past `MessageCitation` rows that point at one of these chunks are
    updated to `chunk_id = NULL` *before* the chunks are removed: the
    database's own `ON DELETE SET NULL` only fires when the engine enforces
    the foreign key at delete time (Postgres does; the SQLite dev database
    does not by default), so this is done explicitly here rather than
    relied on implicitly, to keep past conversations rendering their
    `document_title_snapshot`/`chunk_position` regardless of the backing
    database.

    Deleting the stored original is idempotent (app.services.storage):
    a file already missing from disk does not raise or abort this
    transaction. Ownership is resolved through the single
    `get_owned_or_404` helper, so an unknown id and another user's document
    both answer a generic 404 with no existence leak.
    """
    doc = get_owned_or_404(db, Document, document_id, user_id, detail="document not found")

    chunk_ids = [row.id for row in db.query(Chunk.id).filter(Chunk.document_id == doc.id).all()]
    if chunk_ids:
        db.query(MessageCitation).filter(MessageCitation.chunk_id.in_(chunk_ids)).update(
            {MessageCitation.chunk_id: None}, synchronize_session=False
        )

    if doc.storage_key:
        storage.delete_original(doc.storage_key)

    db.delete(doc)
    db.commit()
