"""Toolchain-level tests: the app starts, routes exist and auth is wired.

The /auth routes are fully implemented (see tests/test_auth.py for their
behaviour); the /documents and /me/usage routes are also now implemented
(see tests/test_documents.py). These tests stay focused on wiring -- the
OpenAPI app boots, every spec'd route resolves instead of 404ing, and a
protected route rejects a missing or bad token before reaching its handler.
"""

from app.security import create_access_token


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_protected_route_without_token_is_401(client):
    resp = client.get("/me/usage")
    assert resp.status_code == 401


def test_protected_route_with_garbage_token_is_401(client):
    resp = client.get("/me/usage", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_protected_route_with_valid_token_for_unknown_user_is_404(client):
    token = create_access_token(subject="11111111-1111-1111-1111-111111111111")
    resp = client.get("/me/usage", headers={"Authorization": f"Bearer {token}"})
    # Authenticated (past app.security), but no such user exists -- the
    # handler itself (now implemented) answers 404, not 401 or 501.
    assert resp.status_code == 404


def test_documents_list_requires_auth(client):
    assert client.get("/documents").status_code == 401


def test_conversations_list_requires_auth(client):
    assert client.get("/conversations").status_code == 401


def test_chunks_lookup_requires_auth(client):
    resp = client.get("/chunks/11111111-1111-1111-1111-111111111111")
    assert resp.status_code == 401


def test_auth_register_needs_no_token_and_is_implemented(client):
    resp = client.post("/auth/register", json={"email": "a@example.com", "password": "Password1"})
    assert resp.status_code == 202


def test_auth_login_validates_its_request_body(client):
    # Malformed email never reaches the handler -- Pydantic rejects it first.
    resp = client.post("/auth/login", json={"email": "not-an-email", "password": "x"})
    assert resp.status_code == 422


def test_openapi_document_serves(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    for path in (
        "/auth/register",
        "/auth/verify",
        "/auth/login",
        "/auth/password-reset/request",
        "/auth/password-reset/confirm",
        "/me/usage",
        "/documents",
        "/documents/{document_id}",
        "/conversations",
        "/conversations/{conversation_id}",
        "/conversations/{conversation_id}/messages",
        "/chunks/{chunk_id}",
    ):
        assert path in paths, f"{path} missing from the generated OpenAPI document"
