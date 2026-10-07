"""Shared pytest fixtures: a single TestClient against the real app.

Deliberately thin: the handlers under test read `app.database.get_db`
directly against the real engine, so each test module manages its own data
lifecycle with an autouse `_clean_state` fixture (see test_documents.py,
test_auth.py, test_chunks.py) rather than this file swapping in a parallel
test database the routers never actually use.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)
