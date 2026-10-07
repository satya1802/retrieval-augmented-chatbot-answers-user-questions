"""Unit tests for `get_owned_or_404` (app/dependencies.py).

Exercised against a real SQLite session and the `Document` model (which has
an `owner_id` column, like every owned row the helper is meant to protect)
rather than mocking the ORM, so the tests prove the owner filter happens at
the query level and not in a Python check layered on top.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.dependencies import get_owned_or_404
from app.models import Document, User


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, future=True
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


def _make_user(db: Session) -> User:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_document(db: Session, owner: User, title: str = "doc") -> Document:
    document = Document(
        owner_id=owner.id,
        title=title,
        file_type="pdf",
        storage_key="s3://bucket/key",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_returns_the_row_when_owner_matches(db: Session) -> None:
    owner = _make_user(db)
    document = _make_document(db, owner)

    result = get_owned_or_404(db, Document, document.id, owner.id)

    assert result.id == document.id


def test_404_when_resource_id_does_not_exist(db: Session) -> None:
    owner = _make_user(db)

    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Document, uuid.uuid4(), owner.id)

    assert exc_info.value.status_code == 404


def test_404_not_403_when_resource_belongs_to_another_owner(db: Session) -> None:
    owner = _make_user(db)
    other_owner = _make_user(db)
    document = _make_document(db, owner)

    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Document, document.id, other_owner.id)

    # A 403 would confirm the row exists at all; the helper must answer the
    # same 404 it gives for a resource_id nobody owns.
    assert exc_info.value.status_code == 404


def test_not_found_and_wrong_owner_share_the_same_generic_detail(db: Session) -> None:
    owner = _make_user(db)
    other_owner = _make_user(db)
    document = _make_document(db, owner)

    with pytest.raises(HTTPException) as missing_exc:
        get_owned_or_404(db, Document, uuid.uuid4(), owner.id)
    with pytest.raises(HTTPException) as wrong_owner_exc:
        get_owned_or_404(db, Document, document.id, other_owner.id)

    assert missing_exc.value.detail == wrong_owner_exc.value.detail


def test_default_detail_message_is_generic(db: Session) -> None:
    owner = _make_user(db)

    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Document, uuid.uuid4(), owner.id)

    assert exc_info.value.detail == "not found"


def test_custom_detail_message_is_used_when_supplied(db: Session) -> None:
    owner = _make_user(db)

    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Document, uuid.uuid4(), owner.id, detail="document not found")

    assert exc_info.value.detail == "document not found"
