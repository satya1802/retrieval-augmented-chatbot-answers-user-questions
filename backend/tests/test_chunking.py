"""Unit tests for backend/app/services/chunking.py.

chunk_text is documented as a pure function: given text, chunk_size and
overlap, it returns consecutive, overlapping slices such that a sentence
split across a chunk boundary still reads wholly inside at least one
chunk, empty/whitespace-only input yields no chunks, and chunk_size must
be positive. These tests exercise that contract directly, not any
private helper underneath it.
"""

import pytest

from app.services.chunking import chunk_text


def test_empty_string_returns_no_chunks():
    assert chunk_text("", chunk_size=10, overlap=2) == []


def test_whitespace_only_returns_no_chunks():
    assert chunk_text("   \n\t  ", chunk_size=10, overlap=2) == []


def test_text_shorter_than_chunk_size_returns_single_chunk():
    text = "short text"
    result = chunk_text(text, chunk_size=1000, overlap=200)
    assert result == [text]


def test_leading_and_trailing_whitespace_is_stripped():
    result = chunk_text("  hello world  ", chunk_size=1000, overlap=0)
    assert result == ["hello world"]


def test_chunks_do_not_exceed_chunk_size():
    text = "a" * 2500
    result = chunk_text(text, chunk_size=1000, overlap=200)
    assert all(len(chunk) <= 1000 for chunk in result)


def test_multiple_chunks_produced_for_long_text():
    text = "a" * 2500
    result = chunk_text(text, chunk_size=1000, overlap=200)
    assert len(result) > 1


def test_consecutive_chunks_share_overlap_characters():
    # Overlap guarantees that the tail of one chunk reappears at the head
    # of the next, so a sentence split at the boundary is still wholly
    # readable inside one chunk.
    text = "0123456789" * 50  # 500 chars
    chunk_size = 100
    overlap = 20
    result = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    assert len(result) > 1
    for i in range(len(result) - 1):
        tail = result[i][-overlap:]
        head = result[i + 1][:overlap]
        assert tail == head


def test_sentence_split_across_boundary_is_whole_in_one_chunk():
    # A 10-character sentence sits straddling the boundary between the
    # first non-overlapping window (0-40) and the second overlapping
    # chunk (25-60): chunk_size=40, overlap=15 means consecutive chunks
    # start 25 characters apart, so the chunk starting at 25 contains the
    # sentence (positions 50-60) wholly, even though the first chunk
    # (0-40) cuts it off entirely.
    sentence = "fox jumps."
    padding = "x" * 50
    text = padding + sentence
    result = chunk_text(text, chunk_size=40, overlap=15)
    assert any(sentence in chunk for chunk in result)


def test_zero_overlap_produces_non_overlapping_chunks():
    text = "a" * 30
    result = chunk_text(text, chunk_size=10, overlap=0)
    assert result == ["a" * 10, "a" * 10, "a" * 10]


def test_negative_overlap_is_clamped_to_zero():
    text = "a" * 30
    result = chunk_text(text, chunk_size=10, overlap=-5)
    assert result == ["a" * 10, "a" * 10, "a" * 10]


def test_overlap_greater_than_or_equal_to_chunk_size_is_clamped():
    # effective_overlap is clamped to chunk_size - 1 so the step always
    # advances and the function cannot loop forever.
    text = "a" * 30
    result = chunk_text(text, chunk_size=10, overlap=10)
    assert len(result) > 0
    assert all(len(chunk) <= 10 for chunk in result)
    # Must terminate and make forward progress -- this would hang if
    # overlap were not clamped below chunk_size.
    assert len(result) <= 30


def test_chunk_size_zero_raises_value_error():
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=0, overlap=0)


def test_chunk_size_negative_raises_value_error():
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=-10, overlap=0)


def test_reassembled_chunks_cover_all_characters_of_stripped_text():
    # Every distinct character of the stripped original text should
    # appear somewhere in the chunk sequence (allowing for overlap
    # duplication), and the sequence should start where the text does.
    text = "abcdefghij" * 10  # 100 chars, no whitespace
    result = chunk_text(text, chunk_size=15, overlap=5)
    joined = "".join(result)
    for ch in set(text):
        assert ch in joined
    assert result[0][0] == text[0]


def test_single_character_text():
    assert chunk_text("x", chunk_size=10, overlap=5) == ["x"]


def test_text_exactly_chunk_size_returns_single_chunk():
    text = "a" * 10
    result = chunk_text(text, chunk_size=10, overlap=3)
    assert result == [text]
