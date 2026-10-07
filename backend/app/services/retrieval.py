"""Chunk retrieval for assembling answer context (AC-009, AC-020, AC-024,
AC-035, AC-036, AC-037, AC-039, AC-041).

A single, reusable query builder so every call site -- today just
`POST /conversations/{id}/messages` -- inherits the owner_id predicate for
free and cannot accidentally search another user's chunks when the retrieval
pipeline is built out. It also inherits the "ready documents only" filter,
so a document still processing -- or one that failed -- can never surface a
chunk as context or be cited.

`retrieve_context` is the top-k semantic search built on top of that query:
embed the question through the same `get_embedding_client()` seam used for
chunk embeddings (no second provider path), score every candidate chunk by
cosine similarity -- via pgvector's distance operator on Postgres, or in
Python over the JSON-stored embedding on SQLite -- and return the caller's
highest-scoring `RETRIEVAL_TOP_K` chunks, ordered by score. No keyword/BM25
search and no re-ranking stage exists anywhere in this path.
"""

import math
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Query, Session

from app.config import RETRIEVAL_TOP_K
from app.models import Chunk, Document
from app.services.embedding_client import get_embedding_client

READY_STATUS = "ready"


def build_context_chunk_query(
    db: Session,
    owner_id: uuid.UUID,
    document_ids: list[uuid.UUID] | None = None,
    limit: int | None = 5,
) -> Query:
    """Chunks visible to `owner_id`, optionally narrowed to `document_ids`.

    Always filters by `Chunk.owner_id` at the query level -- never fetches
    broadly then filters in Python -- so the generated SQL carries the
    ownership predicate a test can assert on directly via `str(query)`. Also
    joins to `Document` and filters on `Document.status == 'ready'` so
    chunks belonging to a still-processing or failed document are excluded
    from retrieval entirely (AC-020, AC-024).

    `limit=None` returns every matching chunk, unordered by score -- used by
    `retrieve_context` as its unbounded candidate scan before scoring.
    """
    query = (
        db.query(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.owner_id == owner_id, Document.status == READY_STATUS)
    )
    if document_ids:
        query = query.filter(Chunk.document_id.in_(document_ids))
    query = query.order_by(Chunk.position)
    return query.limit(limit) if limit is not None else query


@dataclass(frozen=True)
class ContextChunk:
    """One retrieved chunk of answer context, with enough to cite it:
    the document it came from (AC-036) and its position within it."""

    text: str
    document_title: str
    chunk_id: uuid.UUID
    position: int
    score: float


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve_context(
    db: Session,
    owner_id: uuid.UUID,
    question: str,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = RETRIEVAL_TOP_K,
) -> list[ContextChunk]:
    """Embed `question` through `get_embedding_client()` -- the same model
    used for chunk embeddings, no second provider seam (AC-035) -- and
    return the caller's `top_k` highest-scoring ready chunks, in similarity
    order, optionally narrowed to `document_ids` with no fallback to
    unselected documents (AC-039, AC-041).

    Candidates always come from `build_context_chunk_query`'s owner/ready
    predicates, so a processing/failed/other-user chunk is unreachable here
    regardless of how it scores. Returns an empty list, never an error, when
    the owner has no ready chunks with an embedding.
    """
    dialect = db.get_bind().dialect.name

    if dialect == "postgresql":
        has_candidate = (
            build_context_chunk_query(db, owner_id, document_ids=document_ids, limit=1)
            .filter(Chunk.embedding.isnot(None))
            .first()
        )
        if has_candidate is None:
            return []
        vectors = get_embedding_client().embed([question])
        if not vectors:
            return []
        return _score_postgresql(db, owner_id, document_ids, vectors[0], top_k)

    candidates = (
        build_context_chunk_query(db, owner_id, document_ids=document_ids, limit=None)
        .filter(Chunk.embedding.isnot(None))
        .all()
    )
    if not candidates:
        return []
    vectors = get_embedding_client().embed([question])
    if not vectors:
        return []
    return _score_python(candidates, vectors[0], top_k)


def _score_python(
    candidates: list[Chunk], question_vector: list[float], top_k: int
) -> list[ContextChunk]:
    scored = [
        ContextChunk(
            text=chunk.text,
            document_title=chunk.document.title,
            chunk_id=chunk.id,
            position=chunk.position,
            score=_cosine_similarity(question_vector, chunk.embedding),
        )
        for chunk in candidates
    ]
    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]


def _score_postgresql(
    db: Session,
    owner_id: uuid.UUID,
    document_ids: list[uuid.UUID] | None,
    question_vector: list[float],
    top_k: int,
) -> list[ContextChunk]:
    distance = Chunk.embedding.cosine_distance(question_vector)
    query = (
        db.query(Chunk, distance.label("distance"))
        .join(Document, Chunk.document_id == Document.id)
        .filter(
            Chunk.owner_id == owner_id,
            Document.status == READY_STATUS,
            Chunk.embedding.isnot(None),
        )
    )
    if document_ids:
        query = query.filter(Chunk.document_id.in_(document_ids))
    rows = query.order_by(distance).limit(top_k).all()
    return [
        ContextChunk(
            text=chunk.text,
            document_title=chunk.document.title,
            chunk_id=chunk.id,
            position=chunk.position,
            score=1.0 - dist,
        )
        for chunk, dist in rows
    ]
