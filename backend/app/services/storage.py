"""Local-filesystem storage for original uploaded files, keyed by owner.

No cloud SDK dependency per this ticket's constraints: swap this module's
body for an S3-backed one later (the approved architecture names AWS S3)
without touching any caller, since they only ever import these three
functions.
"""

import uuid
from pathlib import Path

from app.config import STORAGE_ROOT


def _owner_dir(owner_id: uuid.UUID) -> Path:
    path = Path(STORAGE_ROOT) / str(owner_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_original(
    owner_id: uuid.UUID, document_id: uuid.UUID, filename: str, content: bytes
) -> str:
    """Write `content` under a path keyed by owner and document id.

    Returns the storage key (a filesystem path) to persist on the Document
    row's `storage_key` column.
    """
    safe_name = (filename or "upload").replace("/", "_").replace("\\", "_")
    target = _owner_dir(owner_id) / f"{document_id}_{safe_name}"
    target.write_bytes(content)
    return str(target)


def read_original(storage_key: str) -> bytes:
    return Path(storage_key).read_bytes()


def delete_original(storage_key: str) -> None:
    path = Path(storage_key)
    if path.exists():
        path.unlink()
