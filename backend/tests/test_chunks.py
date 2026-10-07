"""Tests for GET /chunks/{chunk_id} (AC-071, AC-072, AC-034, AC-008).

Chunks are normally produced by the out-of-request ingestion pipeline
(app/services/ingestion_service.py), which calls a real embedding provider.
Driving that here would make these tests depend on network access and an
API key, so each test inserts its Document/Chunk rows directly through the
same SQLAlchemy session the app uses, and exercises only the router under
test: GET /chunks/{chunk_id}.
"""

import pytest

from app.database import Base, SessionLocal, engine
from app.models import Chunk, Document, User
from app.services import mailer


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


def _make_chunk(email: str, *, title: str, position: int, text: str) -> Chunk:
    """Insert a Document and one Chunk owned by the user with `email`,
    bypassing the ingestion pipeline entirely."""
    session = SessionLocal()
    try:
        owner = session.query(User).filter(User.email == email).one()
        doc = Document(
            owner_id=owner.id,
            title=title,
            file_type="txt",
            storage_key="unused",
            status="ready",
        )
        session.add(doc)
        session.flush()
        chunk = Chunk(
            document_id=doc.id,
            owner_id=owner.id,
            position=position,
            text=text,
        )
        session.add(chunk)
        session.commit()
        session.refresh(chunk)
        return chunk
    finally:
        session.close()


# ------------------------------------------------------- AC-071/AC-072 ----


def test_get_chunk_returns_text_document_title_and_position(client):
    headers = _auth_headers(client)
    chunk = _make_chunk(
        "owner@example.com", title="Policy Manual.pdf", position=3, text="the relevant passage"
    )

    resp = client.get(f"/chunks/{chunk.id}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "the relevant passage"
    assert body["document_title"] == "Policy Manual.pdf"
    assert body["position"] == 3


# ------------------------------------------------------------- AC-008 -----


def test_get_chunk_owned_by_another_user_is_404(client):
    _auth_headers(client, "owner@example.com")
    other_headers = _auth_headers(client, "other@example.com")
    chunk = _make_chunk(
        "owner@example.com", title="Private.pdf", position=0, text="not for other user"
    )

    resp = client.get(f"/chunks/{chunk.id}", headers=other_headers)

    assert resp.status_code == 404
    # The 404 must not leak the chunk's existence or content.
    assert "not for other user" not in resp.text


def test_get_chunk_unknown_id_is_404(client):
    headers = _auth_headers(client)

    resp = client.get(
        "/chunks/00000000-0000-0000-0000-000000000000", headers=headers
    )

    assert resp.status_code == 404


def test_get_chunk_owner_can_still_fetch_their_own_chunk_after_other_users_404(client):
    """Guards against a filter bug that rejects everyone instead of just
    non-owners (i.e. the owner_id filter is additive, not a blanket deny)."""
    headers = _auth_headers(client, "owner@example.com")
    chunk = _make_chunk(
        "owner@example.com", title="Mine.pdf", position=1, text="my own content"
    )

    resp = client.get(f"/chunks/{chunk.id}", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["text"] == "my own content"


# --------------------------------------------------------------- auth -----


def test_get_chunk_requires_auth(client):
    resp = client.get("/chunks/00000000-0000-0000-0000-000000000000")

    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


def test_get_chunk_rejects_malformed_chunk_id(client):
    headers = _auth_headers(client)

    resp = client.get("/chunks/not-a-uuid", headers=headers)

    assert resp.status_code == 422
