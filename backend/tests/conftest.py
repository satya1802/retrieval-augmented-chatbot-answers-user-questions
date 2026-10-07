"""Shared fixtures for the backend test suite.

`DATABASE_URL` and `STORAGE_ROOT` must be set before anything under `app` is
imported: `app.database` binds its engine to `DATABASE_URL` at import time,
and `app.config` reads `STORAGE_ROOT` the same way, so setting either after
import has no effect. `os.environ.setdefault` is used rather than a plain
assignment so a value already set in the environment (CI, a developer's
shell) wins over this fallback.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid

import pytest
from fastapi.testclient import TestClient

_TEST_DIR = tempfile.mkdtemp(prefix="rag-chatbot-tests-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DIR}/test.db")
os.environ.setdefault("STORAGE_ROOT", f"{_TEST_DIR}/storage")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402,F401  -- import registers every table on Base
from app.main import app  # noqa: E402  -- also runs Base.metadata.create_all on import
from app.models import Document, User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_tables():
    """Every test starts against empty tables; the schema itself persists
    for the whole session, but no row should leak from one test to the next."""
    yield
    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def make_user(db_session):
    def _make_user(**overrides):
        user = User(
            email=overrides.pop("email", f"{uuid.uuid4()}@example.com"),
            password_hash=overrides.pop("password_hash", "hashed"),
            is_verified=overrides.pop("is_verified", True),
            **overrides,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make_user


@pytest.fixture
def make_document(db_session):
    def _make_document(owner, **overrides):
        document = Document(
            owner_id=owner.id,
            title=overrides.pop("title", "Example document.txt"),
            file_type=overrides.pop("file_type", "txt"),
            storage_key=overrides.pop("storage_key", ""),
            status=overrides.pop("status", "processing"),
            **overrides,
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        return document

    return _make_document
