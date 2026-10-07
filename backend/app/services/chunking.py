"""Split extracted document text into overlapping chunks.

Size and overlap are read from `app.config` by callers (the ingestion
service), not hardcoded here, so this module stays a pure function of
whatever values it is given -- the constraint that configuration lives in
one place, not scattered at call sites.
"""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Return consecutive, overlapping slices of `text`'s stripped content.

    Each chunk is at most `chunk_size` characters; consecutive chunks share
    `overlap` trailing/leading characters so a sentence split across a
    boundary still reads wholly inside at least one chunk. Empty or
    whitespace-only input returns no chunks at all -- callers treat that the
    same as "no readable text was found".
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    effective_overlap = min(max(overlap, 0), chunk_size - 1)

    stripped = text.strip()
    if not stripped:
        return []

    chunks: list[str] = []
    length = len(stripped)
    step = chunk_size - effective_overlap
    start = 0
    while start < length:
        end = min(start + chunk_size, length)
        piece = stripped[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start += step
    return chunks
