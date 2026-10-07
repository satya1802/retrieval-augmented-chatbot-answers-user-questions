"""The document ingestion pipeline: extract, chunk, embed, persist, finish.

Enqueued by `POST /documents` as a FastAPI `BackgroundTask` so the client
never holds the upload connection open while this runs (AC-021); it opens
its own database session because the request's session is closed by the
time a background task executes.

Every exit path lands the document in a terminal `ready` or `failed` status.
A failure after chunks have already been written for this document deletes
them first, so a failed document is left with zero chunks in the index and
is still deletable and re-uploadable (AC-023).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.config import CHUNK_OVERLAP, CHUNK_SIZE
from app.database import SessionLocal
from app.models import Chunk, Document
from app.services import storage
from app.services.chunking import chunk_text
from app.services.embedding_client import EmbeddingClient, get_embedding_client
from app.services.text_extraction import ExtractionError, NoReadableText, extract_text

logger = logging.getLogger(__name__)

SCANNED_PDF_MESSAGE = (
    "No readable text was found in this PDF. Scanned documents requiring "
    "OCR are not supported in this version."
)


def run_ingestion(document_id: uuid.UUID, embedding_client: EmbeddingClient | None = None) -> None:
    """Background-task entry point registered by `POST /documents`.

    `embedding_client` is accepted (and defaults to the shared, swappable
    client) so a caller -- a test, for instance -- can pass a fake directly
    without touching global state.
    """
    db = SessionLocal()
    try:
        _ingest(db, document_id, embedding_client or get_embedding_client())
    finally:
        db.close()


def _fail(db: Session, document: Document, reason: str) -> None:
    """Terminal failure: drop any chunks already written for this document
    and record a user-readable reason. Runs in its own commit so a failure
    midway through persistence still leaves a clean, consistent row."""
    db.query(Chunk).filter(Chunk.document_id == document.id).delete()
    document.status = "failed"
    document.failure_reason = reason
    db.add(document)
    db.commit()


def _ingest(db: Session, document_id: uuid.UUID, client: EmbeddingClient) -> None:
    document = db.get(Document, document_id)
    if document is None:
        return  # deleted before ingestion ran; nothing to do

    try:
        content = storage.read_original(document.storage_key)
    except OSError as exc:
        _fail(db, document, f"Could not read the uploaded file: {exc}")
        return

    try:
        text = extract_text(document.file_type, content)
    except NoReadableText:
        _fail(db, document, SCANNED_PDF_MESSAGE)
        return
    except ExtractionError as exc:
        _fail(db, document, f"Could not extract text from this document: {exc}")
        return
    except Exception:  # noqa: BLE001 -- any extractor crash is a failure, never a 500
        logger.exception("unexpected extraction failure for document %s", document_id)
        _fail(db, document, "Could not extract text from this document.")
        return

    pieces = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    if not pieces:
        _fail(db, document, SCANNED_PDF_MESSAGE)
        return

    try:
        vectors = client.embed(pieces)
    except Exception:  # noqa: BLE001 -- provider errors are a failure, never a 500
        logger.exception("embedding failure for document %s", document_id)
        _fail(db, document, "Could not generate embeddings for this document. Please try again.")
        return

    if len(vectors) != len(pieces):
        _fail(db, document, "Embedding provider returned an unexpected number of vectors.")
        return

    try:
        db.query(Chunk).filter(Chunk.document_id == document.id).delete()
        for position, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
            db.add(
                Chunk(
                    document_id=document.id,
                    owner_id=document.owner_id,
                    position=position,
                    text=piece,
                    embedding=vector,
                )
            )
        document.status = "ready"
        document.failure_reason = None
        db.add(document)
        db.commit()
    except Exception:  # noqa: BLE001 -- a persistence failure rolls back fully
        logger.exception("persistence failure for document %s", document_id)
        db.rollback()
        _fail(db, document, "Could not save the processed document. Please try again.")
