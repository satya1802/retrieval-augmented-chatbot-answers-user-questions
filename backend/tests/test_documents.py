"""Tests for the document upload and library API (US-005-1)."""

import io
import zipfile

import pytest

from app.config import DOCUMENTS_CAP
from app.database import Base, engine
from app.services import mailer

PDF_BYTES = b"%PDF-1.4\n%mock pdf content\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


def _docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<xml>hello</xml>")
        zf.writestr("[Content_Types].xml", "<xml/>")
    return buf.getvalue()


def _xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/workbook.xml", "<xml>spreadsheet</xml>")
        zf.writestr("[Content_Types].xml", "<xml/>")
    return buf.getvalue()


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


# ----------------------------------------------------------- AC-014 -------


def test_upload_pdf_stores_it_and_it_appears_in_list(client):
    headers = _auth_headers(client)

    resp = client.post(
        "/documents",
        headers=headers,
        files=[("files", ("report.pdf", PDF_BYTES, "application/pdf"))],
    )
    assert resp.status_code == 202
    body = resp.json()
    assert len(body["documents"]) == 1
    doc = body["documents"][0]
    assert doc["status"] == "processing"
    assert doc["file_type"] == "pdf"
    assert doc["failure_reason"] is None

    listed = client.get("/documents", headers=headers)
    assert listed.status_code == 200
    ids = [d["id"] for d in listed.json()["documents"]]
    assert doc["id"] in ids


def test_upload_docx_and_text_and_markdown(client):
    headers = _auth_headers(client)

    docx_resp = client.post(
        "/documents",
        headers=headers,
        files=[("files", ("notes.docx", _docx_bytes(), "application/vnd.openxml"))],
    )
    assert docx_resp.status_code == 202
    assert docx_resp.json()["documents"][0]["file_type"] == "docx"

    txt_resp = client.post(
        "/documents",
        headers=headers,
        files=[("files", ("plain.txt", b"hello world", "text/plain"))],
    )
    assert txt_resp.status_code == 202
    assert txt_resp.json()["documents"][0]["file_type"] == "txt"

    md_resp = client.post(
        "/documents",
        headers=headers,
        files=[("files", ("readme.md", b"# hello", "text/markdown"))],
    )
    assert md_resp.status_code == 202
    assert md_resp.json()["documents"][0]["file_type"] == "md"


# ----------------------------------------------------------- AC-015 -------


def test_upload_unsupported_type_is_rejected_with_415_and_creates_no_row(client):
    headers = _auth_headers(client)

    resp = client.post(
        "/documents",
        headers=headers,
        files=[("files", ("image.png", PNG_BYTES, "image/png"))],
    )
    assert resp.status_code == 415
    assert "pdf" in resp.json()["detail"].lower()
    assert "docx" in resp.json()["detail"].lower()

    listed = client.get("/documents", headers=headers)
    assert listed.json()["documents"] == []


def test_upload_spreadsheet_disguised_as_pdf_extension_is_rejected_by_content(client):
    """Validation is by sniffed content, not filename extension alone."""
    headers = _auth_headers(client)

    resp = client.post(
        "/documents",
        headers=headers,
        files=[("files", ("sneaky.pdf", _xlsx_bytes(), "application/pdf"))],
    )
    assert resp.status_code == 415

    listed = client.get("/documents", headers=headers)
    assert listed.json()["documents"] == []


# ----------------------------------------------------------- AC-016 -------


def test_no_url_based_upload_path_exists(client):
    headers = _auth_headers(client)

    resp = client.post("/documents", headers=headers, json={"url": "https://example.com/doc.pdf"})
    # No multipart file supplied: FastAPI rejects the request before any
    # handler logic runs, and certainly never accepts a URL as the source.
    assert resp.status_code in (400, 415, 422)

    listed = client.get("/documents", headers=headers)
    assert listed.json()["documents"] == []


# ----------------------------------------------------------- AC-017 -------


def test_multi_file_upload_creates_independent_rows_and_bad_file_does_not_block_others(client):
    headers = _auth_headers(client)

    resp = client.post(
        "/documents",
        headers=headers,
        files=[
            ("files", ("good1.txt", b"first document", "text/plain")),
            ("files", ("bad.png", PNG_BYTES, "image/png")),
            ("files", ("good2.pdf", PDF_BYTES, "application/pdf")),
        ],
    )
    assert resp.status_code == 202
    body = resp.json()
    assert len(body["documents"]) == 2
    ids = {d["id"] for d in body["documents"]}
    assert len(ids) == 2
    for doc in body["documents"]:
        assert doc["status"] == "processing"
        assert doc["failure_reason"] is None

    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["filename"] == "bad.png"

    listed = client.get("/documents", headers=headers)
    assert len(listed.json()["documents"]) == 2


# ------------------------------------------------------- document cap -----


def test_exceeding_document_cap_returns_409_naming_the_cap(client, monkeypatch):
    import app.routers.documents as documents_module

    monkeypatch.setattr(documents_module, "DOCUMENTS_CAP", 1)
    headers = _auth_headers(client)

    first = client.post(
        "/documents",
        headers=headers,
        files=[("files", ("one.txt", b"first", "text/plain"))],
    )
    assert first.status_code == 202

    second = client.post(
        "/documents",
        headers=headers,
        files=[("files", ("two.txt", b"second", "text/plain"))],
    )
    assert second.status_code == 409
    assert "1" in second.json()["detail"]

    listed = client.get("/documents", headers=headers)
    assert len(listed.json()["documents"]) == 1


# --------------------------------------------------------- ownership ------


def test_list_and_get_are_scoped_to_the_caller(client):
    owner_headers = _auth_headers(client, "owner2@example.com")
    other_headers = _auth_headers(client, "other2@example.com")

    upload = client.post(
        "/documents",
        headers=owner_headers,
        files=[("files", ("mine.txt", b"owner content", "text/plain"))],
    )
    doc_id = upload.json()["documents"][0]["id"]

    other_list = client.get("/documents", headers=other_headers)
    assert other_list.json()["documents"] == []

    other_get = client.get(f"/documents/{doc_id}", headers=other_headers)
    assert other_get.status_code == 404

    owner_get = client.get(f"/documents/{doc_id}", headers=owner_headers)
    assert owner_get.status_code == 200
    assert owner_get.json()["id"] == doc_id


def test_get_unknown_document_is_404(client):
    headers = _auth_headers(client)
    resp = client.get("/documents/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 404


# ------------------------------------------------------------- usage ------


def test_me_usage_reports_documents_cap_and_remaining_questions(client):
    headers = _auth_headers(client, "usage@example.com")

    client.post(
        "/documents",
        headers=headers,
        files=[("files", ("one.txt", b"content", "text/plain"))],
    )

    resp = client.get("/me/usage", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_count"] == 1
    assert body["documents_cap"] == DOCUMENTS_CAP
    assert "remaining_questions" in body
    assert "reset_date" in body


def test_endpoints_require_auth(client):
    resp = client.get("/documents")
    assert resp.status_code == 401
    resp = client.get("/me/usage")
    assert resp.status_code == 401
