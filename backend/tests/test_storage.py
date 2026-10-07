"""Unit tests for app/services/storage.py.

This ticket carries no acceptance criteria of its own (see ticket text), so
these tests exercise the module's documented contract instead: `save_original`
writes bytes under a path keyed by owner id and returns the storage key to
persist, `read_original` returns exactly what was written for that key, and
`delete_original` removes the file and is a no-op (not an error) when the
key no longer points at anything -- since callers may retry a cleanup.

Each test points the module at a fresh `tmp_path` via monkeypatch rather than
the real `STORAGE_ROOT`, so the suite never touches the developer's working
directory and tests do not see each other's files.
"""

import uuid
from pathlib import Path

import pytest

from app.services import storage


@pytest.fixture(autouse=True)
def isolated_storage_root(tmp_path, monkeypatch):
    """Redirect every test in this module at a scratch directory."""
    monkeypatch.setattr(storage, "STORAGE_ROOT", str(tmp_path))
    return tmp_path


def test_save_original_writes_the_given_bytes_under_the_owner(isolated_storage_root):
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()
    content = b"hello world"

    key = storage.save_original(owner_id, document_id, "notes.txt", content)

    written = Path(key)
    assert written.exists()
    assert written.read_bytes() == content
    # Keyed by owner: the file lives directly under a directory named for
    # the owner id (not nested any further, not a sibling of it).
    assert written.parent == isolated_storage_root / str(owner_id)


def test_save_original_returns_a_key_that_read_original_round_trips(isolated_storage_root):
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()
    content = b"\x00binary\xffcontent"

    key = storage.save_original(owner_id, document_id, "report.pdf", content)

    assert storage.read_original(key) == content


def test_save_original_includes_the_document_id_and_filename_in_the_key():
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()

    key = storage.save_original(owner_id, document_id, "quarterly.md", b"data")

    assert str(document_id) in key
    assert "quarterly.md" in key


def test_save_original_does_not_let_a_slash_in_the_filename_escape_the_owner_dir(
    isolated_storage_root,
):
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()

    key = storage.save_original(owner_id, document_id, "../../etc/passwd", b"data")

    written = Path(key)
    # The slash-bearing filename did not create (or write into) any
    # directory other than the owner's own: the written file still lives
    # one level directly under the owner directory.
    assert written.parent == isolated_storage_root / str(owner_id)
    assert "/" not in written.name


def test_save_original_sanitizes_backslashes_in_the_filename():
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()

    key = storage.save_original(owner_id, document_id, "weird\\name.txt", b"data")

    written = Path(key)
    assert written.parent.name == str(owner_id)
    assert "\\" not in written.name


def test_save_original_falls_back_to_a_default_name_for_an_empty_filename():
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()

    key = storage.save_original(owner_id, document_id, "", b"data")

    assert "upload" in key


def test_save_original_keeps_different_owners_in_separate_directories():
    owner_a = uuid.uuid4()
    owner_b = uuid.uuid4()
    document_id = uuid.uuid4()

    key_a = storage.save_original(owner_a, document_id, "same.txt", b"a-content")
    key_b = storage.save_original(owner_b, document_id, "same.txt", b"b-content")

    assert key_a != key_b
    assert storage.read_original(key_a) == b"a-content"
    assert storage.read_original(key_b) == b"b-content"


def test_delete_original_removes_the_file(isolated_storage_root):
    owner_id = uuid.uuid4()
    document_id = uuid.uuid4()
    key = storage.save_original(owner_id, document_id, "to-delete.txt", b"data")

    storage.delete_original(key)

    assert not Path(key).exists()
    with pytest.raises(FileNotFoundError):
        storage.read_original(key)


def test_delete_original_is_a_no_op_for_a_missing_key(isolated_storage_root):
    missing_key = str(isolated_storage_root / "nonexistent-owner" / "nonexistent-file.txt")

    # Must not raise even though nothing was ever written at this key.
    storage.delete_original(missing_key)
