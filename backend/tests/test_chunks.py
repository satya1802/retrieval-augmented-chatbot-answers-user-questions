"""Unit tests for backend/app/routers/chunks.py: the single GET /chunks/{id}
lookup used to inspect a citation's source passage (AC-071, AC-072), scoped
to the caller the same way every owned resource is (AC-008), and collapsing
"never existed", "not yours" and "its document was deleted" into one
indistinguishable 404 (AC-034).

There is no endpoint that creates a chunk directly -- only document
ingestion does -- so `_seed_chunk` below inserts a Document/Chunk pair
straight through a session, the same shortcut app.services.ingestion_service
itself uses to persist chunks.
"""

import uuid

import pytest

from app.database import Base, engine
from app.database import SessionLocal as _SessionLocal
from app.models import Chunk, Document, User
from app.services import mailer

# The exact body app/routers/chunks.py answers with for every 404 case --
# asserted against literally below, never imported from the router, so a
# test failure here means the *observable* contract changed, not just an
# internal refactor.
_NOT_FOUND_DETAIL = "source document is no longer available"


@pytest.fixture(autouse=True)
def _clean_state():
    mailer.OUTBOX.clear()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


def _latest_token() -> str:
    assert mailer.OUTBOX, "no email was sent"
    return mailer.OUTBOX[-1].body.rsplit(" ", 1)[-1].strip()


def _auth_headers(client, email="owner@example.com", password="Password1") -> dict:
    client.post("/auth/register", json={"email": email, "password": password})
    token = _latest_token()
    client.post("/auth/verify", json={"token": token})
    login = client.post("/auth/login", json={"email": email, "password": password})
    access_token = login.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def _seed_chunk(
    email: str,
    title: str = "Report.pdf",
    text: str = "the chunk text",
    position: int = 0,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a ready Document and one owned Chunk for `email`'s user row.
    Returns (chunk_id, document_id)."""
    with _SessionLocal() as db:
        owner = db.query(User).filter(User.email == email).one()
        document = Document(
            owner_id=owner.id, title=title, file_type="pdf", storage_key="k", status="ready"
        )
        db.add(document)
        db.flush()
        chunk = Chunk(document_id=document.id, owner_id=owner.id, position=position, text=text)
        db.add(chunk)
        db.commit()
        return chunk.id, document.id


# ----------------------------------------------------------- AC-071/072 ---


def test_get_owned_chunk_returns_its_text_document_title_and_position(client):
    headers = _auth_headers(client)
    chunk_id, _ = _seed_chunk(
        "owner@example.com", title="Quarterly Report.pdf", text="revenue grew 12%", position=3
    )

    resp = client.get(f"/chunks/{chunk_id}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "text": "revenue grew 12%",
        "document_title": "Quarterly Report.pdf",
        "position": 3,
    }


def test_get_chunk_response_never_leaks_internal_ids(client):
    """The response shape is text/document_title/position only -- no
    chunk_id, document_id or owner_id, which a citation UI has no business
    receiving from this lookup."""
    headers = _auth_headers(client)
    chunk_id, _ = _seed_chunk("owner@example.com")

    resp = client.get(f"/chunks/{chunk_id}", headers=headers)

    assert resp.status_code == 200
    assert set(resp.json().keys()) == {"text", "document_title", "position"}


# ----------------------------------------------------------- AC-008 -------


def test_get_another_users_chunk_is_404_with_the_generic_detail(client):
    _auth_headers(client, "owner@example.com")
    other_headers = _auth_headers(client, "other@example.com")
    chunk_id, _ = _seed_chunk("owner@example.com")

    resp = client.get(f"/chunks/{chunk_id}", headers=other_headers)

    assert resp.status_code == 404
    assert resp.json()["detail"] == _NOT_FOUND_DETAIL


# ----------------------------------------------------------- AC-034 -------


def test_get_unknown_chunk_id_is_404_with_the_same_generic_detail(client):
    headers = _auth_headers(client)

    resp = client.get(f"/chunks/{uuid.uuid4()}", headers=headers)

    assert resp.status_code == 404
    assert resp.json()["detail"] == _NOT_FOUND_DETAIL


def test_get_chunk_whose_document_was_deleted_is_404_with_the_same_generic_detail(client):
    """Deleting the parent document cascades the chunk row away entirely
    (app.models.Chunk.document relationship, cascade="all, delete-orphan"
    on Document.chunks): by the time this lookup runs there is no row left
    to tell apart from an id that never existed, and the response proves it
    answers identically either way (AC-034)."""
    headers = _auth_headers(client)
    chunk_id, document_id = _seed_chunk("owner@example.com")

    delete_resp = client.delete(f"/documents/{document_id}", headers=headers)
    assert delete_resp.status_code == 204

    resp = client.get(f"/chunks/{chunk_id}", headers=headers)

    assert resp.status_code == 404
    assert resp.json()["detail"] == _NOT_FOUND_DETAIL


def test_the_three_404_cases_are_byte_identical_responses(client):
    """Unknown id, another user's chunk, and a deleted-document chunk must
    be indistinguishable to the caller -- same status, same body -- or this
    endpoint would leak which of the three actually happened (AC-034)."""
    owner_headers = _auth_headers(client, "owner3@example.com")
    other_headers = _auth_headers(client, "other3@example.com")

    owned_chunk_id, owned_document_id = _seed_chunk("owner3@example.com")
    client.delete(f"/documents/{owned_document_id}", headers=owner_headers)

    unowned_chunk_id, _ = _seed_chunk("other3@example.com")

    deleted_resp = client.get(f"/chunks/{owned_chunk_id}", headers=owner_headers)
    unknown_resp = client.get(f"/chunks/{uuid.uuid4()}", headers=owner_headers)
    unowned_resp = client.get(f"/chunks/{unowned_chunk_id}", headers=owner_headers)

    assert deleted_resp.status_code == unknown_resp.status_code == unowned_resp.status_code == 404
    assert deleted_resp.json() == unknown_resp.json() == unowned_resp.json()


# ----------------------------------------------------------- auth ---------


def test_get_chunk_requires_auth(client):
    resp = client.get(f"/chunks/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_get_chunk_rejects_a_malformed_id_before_any_lookup(client):
    headers = _auth_headers(client)
    resp = client.get("/chunks/not-a-uuid", headers=headers)
    assert resp.status_code == 422
