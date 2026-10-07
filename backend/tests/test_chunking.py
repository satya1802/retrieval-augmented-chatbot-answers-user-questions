"""Unit tests for backend/app/services/chunking.py.

chunk_text is a pure function (no app.config, no I/O), so these tests drive
it directly with explicit chunk_size/overlap arguments rather than through
any service or endpoint -- there is no router in front of it to exercise.

No acceptance criteria were attached to this ticket; coverage below is
derived from the module's own documented contract (its docstring):

- empty/whitespace-only input -> no chunks
- each chunk is at most chunk_size characters
- consecutive chunks share `overlap` characters so a boundary-spanning
  sentence still reads wholly inside at least one chunk
- chunk_size must be positive (ValueError otherwise)
- overlap is clamped into [0, chunk_size - 1] rather than trusted verbatim
- no content of the stripped source text is silently skipped between chunks
"""

import pytest

from app.services.chunking import chunk_text


class TestEmptyInput:
    def test_empty_string_returns_no_chunks(self):
        assert chunk_text("", chunk_size=10, overlap=2) == []

    def test_whitespace_only_returns_no_chunks(self):
        assert chunk_text("   \n\t  ", chunk_size=10, overlap=2) == []


class TestShortText:
    def test_text_shorter_than_chunk_size_returns_single_chunk(self):
        assert chunk_text("hello world", chunk_size=100, overlap=10) == [
            "hello world"
        ]

    def test_surrounding_whitespace_is_stripped(self):
        assert chunk_text("  hello world  \n", chunk_size=100, overlap=10) == [
            "hello world"
        ]

    def test_text_exactly_chunk_size_returns_single_chunk(self):
        text = "a" * 20
        assert chunk_text(text, chunk_size=20, overlap=5) == [text]


class TestChunkSizeBound:
    def test_no_chunk_exceeds_chunk_size(self):
        text = "x" * 2500
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) > 1
        assert all(len(c) <= 100 for c in chunks)

    def test_chunk_size_zero_raises(self):
        with pytest.raises(ValueError):
            chunk_text("some text", chunk_size=0, overlap=0)

    def test_negative_chunk_size_raises(self):
        with pytest.raises(ValueError):
            chunk_text("some text", chunk_size=-5, overlap=0)


class TestOverlapBehaviour:
    def test_consecutive_chunks_share_overlap_characters(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        chunks = chunk_text(text, chunk_size=10, overlap=3)
        assert len(chunks) > 1
        for first, second in zip(chunks, chunks[1:]):
            # the trailing slice of one chunk is a prefix of the next --
            # the overlap claimed by the module's own docstring.
            assert first[-3:] == second[: len(first[-3:])]

    def test_zero_overlap_produces_exact_non_overlapping_chunks(self):
        text = "abcdefghijklmnopqrst"  # 20 chars
        chunks = chunk_text(text, chunk_size=5, overlap=0)
        assert chunks == ["abcde", "fghij", "klmno", "pqrst"]

    def test_negative_overlap_is_treated_as_zero(self):
        text = "abcdefghijklmnopqrst"
        assert chunk_text(text, chunk_size=5, overlap=-10) == chunk_text(
            text, chunk_size=5, overlap=0
        )

    def test_overlap_equal_to_chunk_size_is_clamped_and_terminates(self):
        text = "a" * 50
        # overlap >= chunk_size would make step <= 0 if taken literally,
        # looping forever; the module clamps it to chunk_size - 1 so this
        # must still terminate and make forward progress.
        chunks = chunk_text(text, chunk_size=10, overlap=10)
        assert len(chunks) > 0
        assert all(len(c) <= 10 for c in chunks)

    def test_overlap_far_exceeding_chunk_size_is_clamped_and_terminates(self):
        text = "a" * 50
        chunks = chunk_text(text, chunk_size=10, overlap=9999)
        assert len(chunks) > 0
        assert all(len(c) <= 10 for c in chunks)


class TestBoundarySpanningContent:
    def test_word_split_by_a_naive_boundary_reads_wholly_in_one_chunk(self):
        # Construct text where a chunk_size-based split with no overlap
        # would cut the word "SENTINEL" in half, and confirm overlap keeps
        # it intact in at least one chunk -- the module's stated purpose.
        prefix = "x" * 18
        word = "SENTINEL"
        suffix = "y" * 18
        text = prefix + word + suffix
        chunks = chunk_text(text, chunk_size=20, overlap=10)
        assert any(word in c for c in chunks)

    def test_no_character_of_the_source_is_skipped_between_chunks(self):
        text = "The quick brown fox jumps over the lazy dog, repeatedly, " * 5
        stripped = text.strip()
        chunks = chunk_text(stripped, chunk_size=30, overlap=10)
        full_concat = "".join(chunks)
        # Every 5-character window of the source must show up somewhere in
        # the concatenation of chunks -- if the walk ever advanced past a
        # gap, some window here would go missing.
        for i in range(0, len(stripped) - 5, 5):
            window = stripped[i : i + 5]
            assert window in full_concat, f"missing window {window!r} at {i}"

    def test_chunks_appear_in_source_order(self):
        # Use a strictly increasing marker per 10-character block so each
        # chunk's starting position in the source is unambiguous, even
        # though the block content itself repeats a fixed digit alphabet.
        text = "".join(f"{i:03d}4567890" for i in range(50))  # 500 chars
        chunks = chunk_text(text, chunk_size=50, overlap=5)
        assert len(chunks) > 1
        search_from = 0
        positions = []
        for c in chunks:
            pos = text.index(c[:5], search_from)
            positions.append(pos)
            search_from = pos
        assert positions == sorted(positions)
