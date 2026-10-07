"""Unit tests for `app.services.ingestion_service`.

The ticket carries no acceptance criteria of its own; the module's
docstring is the specification used here: every exit path lands the
document in a terminal `ready` or `failed` status, a failure leaves zero
chunks behind for the document (even when chunks already existed), and the
embedding client is an injectable seam so no test needs network access.

Everything below drives `run_ingestion` -- the module's one public, BackgroundTask
entry point -- and then re-reads the row through a fresh session, the way the
real caller (`POST /documents`'s background task) and anything downstream of
it actually observe the result.
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models import Chunk, Document
from app.services import ingestion_service, storage
from app.services.ingestion_service import SCANNED_PDF_MESSAGE, run_ingestion


class FakeEmbeddingClient:
    """A minimal stand-in for `EmbeddingClient`: no network, deterministic
    vectors, and an injectable failure mode."""

    def __init__(self, vectors=None, raises: Exception | None = None):
        self._vectors = vectors
        self._raises = raises
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self._raises is not None:
            raise self._raises
        if self._vectors is not None:
            return self._vectors
        return [[float(i), float(len(text))] for i, text in enumerate(texts)]


def _make_doc_with_content(
    make_user, make_document, content: bytes, file_type: str = "txt", filename: str = "file.txt"
):
    owner = make_user()
    document = make_document(owner=owner, file_type=file_type, title=filename)
    storage_key = storage.save_original(owner.id, document.id, filename, content)
    document.storage_key = storage_key
    with SessionLocal() as session:
        row = session.get(Document, document.id)
        row.storage_key = storage_key
        session.commit()
    return document


def _reload(document_id: uuid.UUID) -> Document:
    with SessionLocal() as session:
        return session.get(Document, document_id)


def _chunks_for(document_id: uuid.UUID) -> list[Chunk]:
    with SessionLocal() as session:
        return (
            session.query(Chunk)
            .filter(Chunk.document_id == document_id)
            .order_by(Chunk.position)
            .all()
        )


# --- success path -----------------------------------------------------------


def test_successful_ingestion_lands_ready_with_chunks_and_no_failure_reason(
    make_user, make_document, monkeypatch
):
    document = _make_doc_with_content(
        make_user, make_document, b"a" * 25, file_type="txt"
    )
    # Small, deterministic chunk boundaries so multiple chunks are produced
    # from a short fixture string rather than depending on the real default
    # CHUNK_SIZE of 1000 characters.
    monkeypatch.setattr(ingestion_service, "CHUNK_SIZE", 10)
    monkeypatch.setattr(ingestion_service, "CHUNK_OVERLAP", 2)
    fake = FakeEmbeddingClient()

    run_ingestion(document.id, embedding_client=fake)

    refreshed = _reload(document.id)
    assert refreshed.status == "ready"
    assert refreshed.failure_reason is None

    chunks = _chunks_for(document.id)
    assert len(chunks) == len(fake.calls[0])
    assert len(chunks) > 1
    assert [c.position for c in chunks] == list(range(len(chunks)))
    # Chunks are scoped to the document's owner directly (denormalized),
    # per app.models.Chunk's comment that retrieval filters by owner_id.
    assert all(c.owner_id == document.owner_id for c in chunks)
    assert chunks[0].embedding == [0.0, float(len(chunks[0].text))]


def test_run_ingestion_falls_back_to_the_shared_client_when_none_is_passed(
    make_user, make_document, monkeypatch
):
    document = _make_doc_with_content(make_user, make_document, b"hello world")
    fake = FakeEmbeddingClient(vectors=[[9.0, 9.0]])
    monkeypatch.setattr(ingestion_service, "get_embedding_client", lambda: fake)

    run_ingestion(document.id)

    refreshed = _reload(document.id)
    assert refreshed.status == "ready"
    assert fake.calls, "the shared client returned by get_embedding_client() must be used"


# --- missing document --------------------------------------------------------


def test_run_ingestion_is_a_no_op_for_a_document_deleted_before_it_ran():
    missing_id = uuid.uuid4()
    # Must not raise, and must not conjure a row into existence.
    run_ingestion(missing_id, embedding_client=FakeEmbeddingClient())
    assert _reload(missing_id) is None


# --- storage failure ----------------------------------------------------------


def test_unreadable_storage_file_fails_the_document_with_a_readable_reason(
    make_user, make_document
):
    owner = make_user()
    document = make_document(owner=owner, storage_key="/nonexistent/path/does-not-exist.txt")

    run_ingestion(document.id, embedding_client=FakeEmbeddingClient())

    refreshed = _reload(document.id)
    assert refreshed.status == "failed"
    assert "Could not read the uploaded file" in refreshed.failure_reason
    assert _chunks_for(document.id) == []


# --- extraction failures ------------------------------------------------------


def test_whitespace_only_document_fails_with_the_scanned_pdf_message(
    make_user, make_document
):
    document = _make_doc_with_content(make_user, make_document, b"   \n\t  ")

    run_ingestion(document.id, embedding_client=FakeEmbeddingClient())

    refreshed = _reload(document.id)
    assert refreshed.status == "failed"
    assert refreshed.failure_reason == SCANNED_PDF_MESSAGE


def test_undecodable_text_file_fails_with_an_extraction_error_reason(
    make_user, make_document
):
    document = _make_doc_with_content(make_user, make_document, b"\xff\xfe\xfa", file_type="txt")

    run_ingestion(document.id, embedding_client=FakeEmbeddingClient())

    refreshed = _reload(document.id)
    assert refreshed.status == "failed"
    assert refreshed.failure_reason.startswith("Could not extract text from this document:")


def test_unexpected_extractor_crash_fails_cleanly_instead_of_raising(
    make_user, make_document, monkeypatch
):
    document = _make_doc_with_content(make_user, make_document, b"some perfectly fine text")

    def _boom(file_type, content):
        raise RuntimeError("extractor exploded")

    monkeypatch.setattr(ingestion_service, "extract_text", _boom)

    run_ingestion(document.id, embedding_client=FakeEmbeddingClient())

    refreshed = _reload(document.id)
    assert refreshed.status == "failed"
    assert refreshed.failure_reason == "Could not extract text from this document."


def test_chunking_that_yields_nothing_fails_with_the_scanned_pdf_message(
    make_user, make_document, monkeypatch
):
    document = _make_doc_with_content(make_user, make_document, b"some perfectly fine text")
    monkeypatch.setattr(ingestion_service, "chunk_text", lambda *a, **k: [])

    run_ingestion(document.id, embedding_client=FakeEmbeddingClient())

    refreshed = _reload(document.id)
    assert refreshed.status == "failed"
    assert refreshed.failure_reason == SCANNED_PDF_MESSAGE


# --- embedding failures --------------------------------------------------------


def test_embedding_provider_failure_fails_the_document_without_raising(
    make_user, make_document
):
    document = _make_doc_with_content(make_user, make_document, b"some perfectly fine text")
    fake = FakeEmbeddingClient(raises=RuntimeError("provider is down"))

    run_ingestion(document.id, embedding_client=fake)

    refreshed = _reload(document.id)
    assert refreshed.status == "failed"
    assert refreshed.failure_reason == (
        "Could not generate embeddings for this document. Please try again."
    )
    assert _chunks_for(document.id) == []


def test_vector_count_mismatch_fails_the_document(make_user, make_document, monkeypatch):
    document = _make_doc_with_content(make_user, make_document, b"some perfectly fine text")
    monkeypatch.setattr(ingestion_service, "CHUNK_SIZE", 8)
    monkeypatch.setattr(ingestion_service, "CHUNK_OVERLAP", 0)
    fake = FakeEmbeddingClient(vectors=[[0.0, 0.0]])  # fewer vectors than chunks

    run_ingestion(document.id, embedding_client=fake)

    refreshed = _reload(document.id)
    assert refreshed.status == "failed"
    assert refreshed.failure_reason == (
        "Embedding provider returned an unexpected number of vectors."
    )


# --- failure always leaves zero chunks behind, even if some already existed ---


def test_a_failure_deletes_chunks_already_written_for_the_document(
    make_user, make_document, db_session
):
    owner = make_user()
    document = _make_doc_with_content(make_user, make_document, b"some perfectly fine text")
    # Simulate a prior, successful ingestion run that left chunks behind.
    db_session.add(
        Chunk(
            document_id=document.id,
            owner_id=document.owner_id,
            position=0,
            text="stale chunk from a previous run",
            embedding=[0.1, 0.2],
        )
    )
    db_session.commit()
    assert len(_chunks_for(document.id)) == 1

    fake = FakeEmbeddingClient(raises=RuntimeError("provider is down"))
    run_ingestion(document.id, embedding_client=fake)

    refreshed = _reload(document.id)
    assert refreshed.status == "failed"
    assert _chunks_for(document.id) == []


def test_re_ingestion_replaces_old_chunks_rather_than_appending(
    make_user, make_document, db_session
):
    document = _make_doc_with_content(make_user, make_document, b"fresh content for re-run")
    db_session.add(
        Chunk(
            document_id=document.id,
            owner_id=document.owner_id,
            position=0,
            text="stale chunk from a previous run",
            embedding=[0.1, 0.2],
        )
    )
    db_session.commit()

    run_ingestion(document.id, embedding_client=FakeEmbeddingClient())

    refreshed = _reload(document.id)
    assert refreshed.status == "ready"
    chunks = _chunks_for(document.id)
    assert all(c.text != "stale chunk from a previous run" for c in chunks)


# --- persistence failure --------------------------------------------------------


def test_persistence_failure_rolls_back_and_lands_failed_not_a_crash(
    make_user, make_document, monkeypatch
):
    document = _make_doc_with_content(make_user, make_document, b"some perfectly fine text")

    real_session_local = ingestion_service.SessionLocal
    calls = {"n": 0}

    def flaky_session_factory():
        session = real_session_local()
        original_commit = session.commit

        def flaky_commit():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("simulated commit failure")
            return original_commit()

        session.commit = flaky_commit
        return session

    monkeypatch.setattr(ingestion_service, "SessionLocal", flaky_session_factory)

    run_ingestion(document.id, embedding_client=FakeEmbeddingClient())

    refreshed = _reload(document.id)
    assert refreshed.status == "failed"
    assert refreshed.failure_reason == (
        "Could not save the processed document. Please try again."
    )
    assert _chunks_for(document.id) == []
