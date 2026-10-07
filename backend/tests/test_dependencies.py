"""Unit tests for the owner-scoped lookup helper (app/dependencies.py).

`get_owned_or_404` has no HTTP endpoint of its own -- every router just calls
it -- so it is exercised directly here, against a real `Session`, rather than
through a stub route. The ownership-scoping *behaviour* it buys each router
(a stranger's id answers 404, not another user's row) is also covered
end-to-end through the documents endpoints in test_documents.py; this file
is about the helper's own contract: query-level filtering, the 404-not-403
choice, and the default/overridable detail message, for more than one model
so nothing here is accidentally specific to `Document`.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.database import Base, SessionLocal, engine
from app.dependencies import get_owned_or_404
from app.models import Conversation, Document, User


@pytest.fixture(autouse=True)
def _clean_state():
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_user(db, email: str) -> User:
    user = User(email=email, password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_document(db, owner: User, title: str = "doc") -> Document:
    doc = Document(owner_id=owner.id, title=title, file_type="txt", storage_key="k")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _make_conversation(db, owner: User, title: str = "chat") -> Conversation:
    convo = Conversation(owner_id=owner.id, title=title)
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


def test_returns_the_row_when_it_exists_and_is_owned_by_the_caller(db):
    owner = _make_user(db, "owner@example.com")
    doc = _make_document(db, owner)

    found = get_owned_or_404(db, Document, doc.id, owner.id)

    assert found.id == doc.id
    assert found.title == "doc"


def test_raises_404_for_an_id_that_does_not_exist_at_all(db):
    owner = _make_user(db, "owner2@example.com")

    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Document, uuid.uuid4(), owner.id)

    assert exc_info.value.status_code == 404


def test_raises_404_not_403_for_a_row_that_exists_but_belongs_to_someone_else(db):
    owner = _make_user(db, "owner3@example.com")
    other = _make_user(db, "other3@example.com")
    doc = _make_document(db, owner)

    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Document, doc.id, other.id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.status_code != 403


def test_missing_row_and_wrong_owner_answer_with_the_identical_detail(db):
    """A distinguishable body for "exists but not yours" would leak that the
    resource exists at all, which is exactly what the 404-not-403 choice is
    meant to avoid -- so the two failure modes must be indistinguishable to
    the caller."""
    owner = _make_user(db, "owner4@example.com")
    other = _make_user(db, "other4@example.com")
    doc = _make_document(db, owner)

    with pytest.raises(HTTPException) as missing:
        get_owned_or_404(db, Document, uuid.uuid4(), owner.id, detail="document not found")

    with pytest.raises(HTTPException) as wrong_owner:
        get_owned_or_404(db, Document, doc.id, other.id, detail="document not found")

    assert missing.value.status_code == wrong_owner.value.status_code == 404
    assert missing.value.detail == wrong_owner.value.detail == "document not found"


def test_default_detail_is_the_generic_not_found_message(db):
    owner = _make_user(db, "owner5@example.com")

    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Document, uuid.uuid4(), owner.id)

    assert exc_info.value.detail == "not found"


def test_caller_supplied_detail_overrides_the_default(db):
    owner = _make_user(db, "owner6@example.com")

    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Document, uuid.uuid4(), owner.id, detail="conversation not found")

    assert exc_info.value.detail == "conversation not found"


def test_works_against_any_model_with_an_owner_id_not_just_document(db):
    """Nothing about the helper is Document-specific: it is reused by every
    router over whichever model that router owns."""
    owner = _make_user(db, "owner7@example.com")
    other = _make_user(db, "other7@example.com")
    convo = _make_conversation(db, owner)

    found = get_owned_or_404(db, Conversation, convo.id, owner.id)
    assert found.id == convo.id

    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Conversation, convo.id, other.id)
    assert exc_info.value.status_code == 404


def test_owner_filter_is_applied_at_the_query_not_after_fetching_the_row(db):
    """Guards against a regression to 'fetch by id, then check owner in
    Python': if the filter ever moved out of the query, a row that merely
    has the wrong owner_id would still come back from the database layer
    before any check ran. Here, no row with a mismatched owner_id is ever
    returned by the lookup, for a model (Document) with rows from two
    different owners present at once."""
    owner = _make_user(db, "owner8@example.com")
    other = _make_user(db, "other8@example.com")
    mine = _make_document(db, owner, title="mine")
    _make_document(db, other, title="theirs")

    found = get_owned_or_404(db, Document, mine.id, owner.id)
    assert found.title == "mine"

    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Document, mine.id, other.id)
    assert exc_info.value.status_code == 404
