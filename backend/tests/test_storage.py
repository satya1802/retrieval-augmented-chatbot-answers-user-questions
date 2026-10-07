"""Unit tests for app/services/storage.py.

These exercise the module directly rather than through the /documents
router (see test_documents.py for the integration-level coverage of
upload/list/get), since this ticket is specifically about the storage
service's own read/write/delete contract: the thing a later S3-backed
rewrite has to preserve for its callers.
"""

import uuid
from pathlib import Path

import pytest

from app.services import storage


@pytest.fixture(autouse=True)
def _isolated_storage_root(tmp_path, monkeypatch):
    """Point the module at a scratch directory for every test.

    `storage.STORAGE_ROOT` is read inside `_owner_dir` via the module-level
    name bound at import time, so we patch that name directly rather than
    `app.config.STORAGE_ROOT` (which nothing re-reads after import).
    """
    monkeypatch.setattr(storage, "STORAGE_ROOT", str(tmp_path))
    return tmp_path


def test_save_original_writes_bytes_retrievable_by_the_returned_key():
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()
    content = b"hello world, this is the document body"

    key = storage.save_original(owner_id, document_id, "report.pdf", content)

    assert storage.read_original(key) == content


def test_save_original_creates_a_directory_scoped_to_the_owner(tmp_path):
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()

    key = storage.save_original(owner_id, document_id, "notes.txt", b"data")

    owner_dir = tmp_path / str(owner_id)
    assert owner_dir.is_dir()
    assert Path(key).parent == owner_dir


def test_two_owners_get_independent_storage_directories(tmp_path):
    owner_a = uuid.uuid4()
    owner_b = uuid.uuid4()
    document_id = uuid.uuid4()

    key_a = storage.save_original(owner_a, document_id, "same-name.txt", b"owner a's content")
    key_b = storage.save_original(owner_b, document_id, "same-name.txt", b"owner b's content")

    assert key_a != key_b
    assert storage.read_original(key_a) == b"owner a's content"
    assert storage.read_original(key_b) == b"owner b's content"


def test_filename_with_path_separators_is_sanitized_and_cannot_escape_owner_dir(tmp_path):
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()

    key = storage.save_original(owner_id, document_id, "../../etc/passwd", b"malicious")

    owner_dir = tmp_path / str(owner_id)
    assert Path(key).parent == owner_dir
    assert "/" not in Path(key).name.replace(str(document_id), "")
    # the escaped segments were flattened into the filename, not followed
    assert not (tmp_path / "etc").exists()


def test_filename_with_backslashes_is_sanitized():
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()

    key = storage.save_original(owner_id, document_id, "folder\\file.txt", b"content")

    assert "\\" not in Path(key).name


def test_missing_filename_falls_back_to_default_name():
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()

    key = storage.save_original(owner_id, document_id, "", b"content")

    assert "upload" in Path(key).name
    assert storage.read_original(key) == b"content"


def test_saving_again_under_the_same_document_id_and_name_overwrites():
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()

    first_key = storage.save_original(owner_id, document_id, "doc.txt", b"version one")
    second_key = storage.save_original(owner_id, document_id, "doc.txt", b"version two")

    assert first_key == second_key
    assert storage.read_original(second_key) == b"version two"


def test_read_original_of_an_unknown_key_raises():
    with pytest.raises(FileNotFoundError):
        storage.read_original("/no/such/path/that/exists.txt")


def test_delete_original_removes_the_file_so_it_can_no_longer_be_read():
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()
    key = storage.save_original(owner_id, document_id, "doc.txt", b"content")

    storage.delete_original(key)

    assert not Path(key).exists()
    with pytest.raises(FileNotFoundError):
        storage.read_original(key)


def test_delete_original_on_a_missing_file_does_not_raise():
    storage.delete_original("/no/such/path/that/exists.txt")
