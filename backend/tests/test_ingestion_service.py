"""Unit tests for app/services/ingestion_service.py.

No AC numbers are attached to this ticket, so the behaviours covered below
come straight from the module's own docstring and code: every exit path
lands a document in a terminal ready/failed status, a failure never raises
past `run_ingestion` (so the background task never crashes), a failure
clears any chunks already written for that document, and the public entry
point used by `POST /documents` (`run_ingestion(document_id)`, no db/client
args) opens its own session and falls back to the shared embedding client.

Documents are inserted directly through `SessionLocal`, the same way
test_chunks.py does it, rather than through the upload endpoint: that keeps
these tests about the ingestion pipeline alone, not auth or multipart
upload. The embedding provider is always a fake -- never the real,
network-calling `EmbeddingClient` -- so these tests run with no API key and
no network access.
"""

import uuid

import pytest

from app.database import Base, SessionLocal, engine
from app.models import Chunk, Document, User
from app.services import ingestion_service, storage
from app.services.chunking import chunk_text
from app.services.embedding_client import set_embedding_client
from app.services.ingestion_service import SCANNED_PDF_MESSAGE, run_ingestion


@pytest.fixture(autouse=True)
def _clean_state():
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


class FakeEmbeddingClient:
    """A stand-in for `EmbeddingClient` with no network and no API key.

    Records every batch it was asked to embed so a test can assert the
    pipeline called it with exactly the chunk pieces, in order.
    """

    def __init__(self, *, fail: bool = False, mismatch: bool = False, dims: int = 2):
        self.fail = fail
        self.mismatch = mismatch
        self.dims = dims
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.fail:
            raise RuntimeError("embedding provider is down")
        vectors = [[float(i), float(i) + 0.5][: self.dims] for i in range(len(texts))]
        if self.mismatch and vectors:
            vectors = vectors[:-1]
        return vectors


class _FlakyCommitSession:
    """Wraps a real session but fails only its first `.commit()` call, so a
    test can exercise the pipeline's rollback-and-fail path without mocking
    SQLAlchemy out entirely. Every other attribute (query, add, rollback,
    close, get, ...) passes straight through to the real session."""

    def __init__(self, inner):
        self._inner = inner
        self._commit_calls = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def commit(self):
        self._commit_calls += 1
        if self._commit_calls == 1:
            raise RuntimeError("simulated commit failure")
        self._inner.commit()


def _make_document(
    content: bytes, *, file_type: str = "txt", filename: str = "file.txt"
) -> uuid.UUID:
    """Create an owning user and a Document row whose storage_key points at
    `content` on disk, the way POST /documents leaves it for the background
    task to pick up."""
    session = SessionLocal()
    try:
        owner = User(
            email=f"owner-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            is_verified=True,
        )
        session.add(owner)
        session.flush()
        doc = Document(
            owner_id=owner.id,
            title=filename,
            file_type=file_type,
            storage_key="",
            status="processing",
        )
        session.add(doc)
        session.flush()
        doc.storage_key = storage.save_original(owner.id, doc.id, filename, content)
        session.add(doc)
        session.commit()
        return doc.id
    finally:
        session.close()


def _make_document_with_missing_file(file_type: str = "txt") -> uuid.UUID:
    """A document row whose storage_key points at a file that was never
    written -- the "storage read failed" case."""
    session = SessionLocal()
    try:
        owner = User(
            email=f"owner-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            is_verified=True,
        )
        session.add(owner)
        session.flush()
        doc = Document(
            owner_id=owner.id,
            title="missing.txt",
            file_type=file_type,
            storage_key="/nonexistent/path/does-not-exist.txt",
            status="processing",
        )
        session.add(doc)
        session.commit()
        return doc.id
    finally:
        session.close()


def _get_document(document_id: uuid.UUID) -> Document:
    session = SessionLocal()
    try:
        return session.get(Document, document_id)
    finally:
        session.close()


def _get_chunks(document_id: uuid.UUID) -> list[Chunk]:
    session = SessionLocal()
    try:
        return (
            session.query(Chunk)
            .filter(Chunk.document_id == document_id)
            .order_by(Chunk.position)
            .all()
        )
    finally:
        session.close()


# ---------------------------------------------------------------- success --


def test_successful_ingestion_persists_chunks_in_order_and_marks_ready(monkeypatch):
    monkeypatch.setattr(ingestion_service, "CHUNK_SIZE", 50)
    monkeypatch.setattr(ingestion_service, "CHUNK_OVERLAP", 10)
    text = "The quick brown fox jumps over the lazy dog. " * 5
    expected_pieces = chunk_text(text, 50, 10)
    assert len(expected_pieces) > 1, "test setup should produce more than one chunk"

    doc_id = _make_document(text.encode("utf-8"))
    fake = FakeEmbeddingClient()

    run_ingestion(doc_id, fake)

    document = _get_document(doc_id)
    assert document.status == "ready"
    assert document.failure_reason is None

    assert fake.calls == [expected_pieces]

    chunks = _get_chunks(doc_id)
    assert [c.text for c in chunks] == expected_pieces
    assert [c.position for c in chunks] == list(range(len(expected_pieces)))
    assert all(c.owner_id == document.owner_id for c in chunks)
    assert chunks[0].embedding == [0.0, 0.5]


# ------------------------------------------------------- missing document --


def test_ingesting_an_already_deleted_document_is_a_noop():
    random_id = uuid.uuid4()

    run_ingestion(random_id, FakeEmbeddingClient())

    assert _get_document(random_id) is None


# -------------------------------------------------------- storage failure --


def test_unreadable_storage_file_marks_document_failed_not_raised():
    doc_id = _make_document_with_missing_file()

    run_ingestion(doc_id, FakeEmbeddingClient())

    document = _get_document(doc_id)
    assert document.status == "failed"
    assert "could not read the uploaded file" in document.failure_reason.lower()
    assert _get_chunks(doc_id) == []


# ------------------------------------------------------ extraction errors --


def test_empty_document_fails_with_the_scanned_pdf_message():
    doc_id = _make_document(b"   \n\t  ")

    run_ingestion(doc_id, FakeEmbeddingClient())

    document = _get_document(doc_id)
    assert document.status == "failed"
    assert document.failure_reason == SCANNED_PDF_MESSAGE


def test_undecodable_text_file_fails_with_an_extraction_error_detail():
    doc_id = _make_document(b"\xff\xfe\x00\x01not valid utf-8")

    run_ingestion(doc_id, FakeEmbeddingClient())

    document = _get_document(doc_id)
    assert document.status == "failed"
    assert document.failure_reason.startswith("Could not extract text from this document:")


def test_unexpected_extractor_crash_is_caught_as_a_failure_not_a_500(monkeypatch):
    def _boom(file_type, content):
        raise RuntimeError("extractor exploded")

    monkeypatch.setattr(ingestion_service, "extract_text", _boom)
    doc_id = _make_document(b"irrelevant, extract_text is mocked out")

    run_ingestion(doc_id, FakeEmbeddingClient())

    document = _get_document(doc_id)
    assert document.status == "failed"
    assert document.failure_reason == "Could not extract text from this document."
    assert _get_chunks(doc_id) == []


def test_text_that_chunks_to_nothing_fails_with_the_scanned_pdf_message(monkeypatch):
    """Defensive branch: even if extraction somehow yields text that chunks
    to zero pieces, the pipeline still fails cleanly instead of embedding
    an empty batch."""
    monkeypatch.setattr(ingestion_service, "chunk_text", lambda text, size, overlap: [])
    doc_id = _make_document(b"some text that extracts fine")

    run_ingestion(doc_id, FakeEmbeddingClient())

    document = _get_document(doc_id)
    assert document.status == "failed"
    assert document.failure_reason == SCANNED_PDF_MESSAGE


# ------------------------------------------------------- embedding errors --


def test_embedding_provider_failure_marks_document_failed_not_raised():
    doc_id = _make_document(b"some perfectly readable text")

    run_ingestion(doc_id, FakeEmbeddingClient(fail=True))

    document = _get_document(doc_id)
    assert document.status == "failed"
    assert document.failure_reason == (
        "Could not generate embeddings for this document. Please try again."
    )
    assert _get_chunks(doc_id) == []


def test_mismatched_vector_count_marks_document_failed(monkeypatch):
    monkeypatch.setattr(ingestion_service, "CHUNK_SIZE", 20)
    monkeypatch.setattr(ingestion_service, "CHUNK_OVERLAP", 5)
    doc_id = _make_document(b"enough distinct text to split into more than one chunk of content")

    run_ingestion(doc_id, FakeEmbeddingClient(mismatch=True))

    document = _get_document(doc_id)
    assert document.status == "failed"
    assert document.failure_reason == (
        "Embedding provider returned an unexpected number of vectors."
    )
    assert _get_chunks(doc_id) == []


# ------------------------------------------------------ persistence / AC-023


def test_persistence_failure_rolls_back_and_leaves_the_document_with_zero_chunks(
    monkeypatch,
):
    monkeypatch.setattr(
        ingestion_service,
        "SessionLocal",
        lambda: _FlakyCommitSession(SessionLocal()),
    )
    doc_id = _make_document(b"some perfectly readable text")

    run_ingestion(doc_id, FakeEmbeddingClient())

    document = _get_document(doc_id)
    assert document.status == "failed"
    assert document.failure_reason == (
        "Could not save the processed document. Please try again."
    )
    assert _get_chunks(doc_id) == []


def test_a_document_that_failed_after_an_earlier_success_is_left_with_zero_chunks():
    """A failed document is left with zero chunks in the index and is still
    deletable and re-uploadable: re-ingesting a previously-`ready` document
    that now fails must not leave its old chunks behind."""
    doc_id = _make_document(b"some perfectly readable text")

    run_ingestion(doc_id, FakeEmbeddingClient())
    assert _get_document(doc_id).status == "ready"
    assert len(_get_chunks(doc_id)) == 1

    run_ingestion(doc_id, FakeEmbeddingClient(fail=True))

    document = _get_document(doc_id)
    assert document.status == "failed"
    assert _get_chunks(doc_id) == []


# --------------------------------------------- the real production call shape


def test_run_ingestion_with_no_client_argument_falls_back_to_the_shared_default():
    """`POST /documents` enqueues `background_tasks.add_task(run_ingestion,
    doc.id)` -- no db session, no client. This exercises that exact call
    shape: `run_ingestion` must open its own session and consult
    `get_embedding_client()`/`set_embedding_client()` rather than requiring
    a caller to pass one in."""
    fake = FakeEmbeddingClient()
    set_embedding_client(fake)
    try:
        doc_id = _make_document(b"some perfectly readable text")

        run_ingestion(doc_id)

        document = _get_document(doc_id)
        assert document.status == "ready"
        assert fake.calls, "the shared default client was never consulted"
        assert len(_get_chunks(doc_id)) == 1
    finally:
        set_embedding_client(None)
