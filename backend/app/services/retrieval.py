"""Chunk retrieval for assembling answer context (AC-009, AC-020, AC-024).

A single, reusable query builder so every call site -- today just
`POST /conversations/{id}/messages` -- inherits the owner_id predicate for
free and cannot accidentally search another user's chunks when the retrieval
pipeline is built out. It also inherits the "ready documents only" filter,
so a document still processing -- or one that failed -- can never surface a
chunk as context or be cited.
"""

import uuid

from sqlalchemy.orm import Query, Session

from app.models import Chunk, Document

READY_STATUS = "ready"


def build_context_chunk_query(
    db: Session,
    owner_id: uuid.UUID,
    document_ids: list[uuid.UUID] | None = None,
    limit: int = 5,
) -> Query:
    """Chunks visible to `owner_id`, optionally narrowed to `document_ids`.

    Always filters by `Chunk.owner_id` at the query level -- never fetches
    broadly then filters in Python -- so the generated SQL carries the
    ownership predicate a test can assert on directly via `str(query)`. Also
    joins to `Document` and filters on `Document.status == 'ready'` so
    chunks belonging to a still-processing or failed document are excluded
    from retrieval entirely (AC-020, AC-024).
    """
    query = (
        db.query(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.owner_id == owner_id, Document.status == READY_STATUS)
    )
    if document_ids:
        query = query.filter(Chunk.document_id.in_(document_ids))
    return query.order_by(Chunk.position).limit(limit)
