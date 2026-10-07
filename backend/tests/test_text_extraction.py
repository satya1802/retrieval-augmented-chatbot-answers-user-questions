"""Unit tests for app/services/text_extraction.py.

These exercise the module's public entry point, `extract_text`, for each of
the four file types `document_service.sniff_file_type` can hand it (pdf,
docx, md, txt), plus the dispatch and error-wrapping behaviour around it.

Where the real parsing library (pypdf / python-docx) can produce the
fixture deterministically -- an empty document, a blank page, garbage bytes
that are not a valid archive -- the test builds real bytes and runs them
through the real library, the same path production traffic takes. Building
a real PDF with an actual text layer needs a PDF-writing library (e.g.
reportlab) that is not part of this project's dependencies, so the one
"PDF has text" case monkeypatches `pypdf.PdfReader` with a double that
returns pages with known text; that test is the only one trading realism
for control, and it only asserts the per-page texts get joined.
"""

from __future__ import annotations

import io

import pytest

from app.services.text_extraction import (
    ExtractionError,
    NoReadableText,
    _SCANNED_PDF_MESSAGE,
    extract_text,
)


# ---------------------------------------------------------------------------
# txt / md -- decode-only path, shared by both extensions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("file_type", ["txt", "md"])
def test_plain_text_types_return_decoded_content(file_type):
    content = "Hello, world!\nSecond line.".encode("utf-8")
    assert extract_text(file_type, content) == "Hello, world!\nSecond line."


@pytest.mark.parametrize("file_type", ["txt", "md"])
def test_plain_text_whitespace_only_raises_no_readable_text(file_type):
    with pytest.raises(NoReadableText):
        extract_text(file_type, b"   \n\t  ")


@pytest.mark.parametrize("file_type", ["txt", "md"])
def test_plain_text_empty_bytes_raises_no_readable_text(file_type):
    with pytest.raises(NoReadableText):
        extract_text(file_type, b"")


@pytest.mark.parametrize("file_type", ["txt", "md"])
def test_plain_text_invalid_utf8_raises_extraction_error(file_type):
    # 0xff 0xfe is not valid UTF-8 on its own.
    with pytest.raises(ExtractionError):
        extract_text(file_type, b"\xff\xfe\x00\x01")


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


def test_unsupported_file_type_raises_extraction_error():
    with pytest.raises(ExtractionError, match="unsupported file type: xlsx"):
        extract_text("xlsx", b"whatever")


# ---------------------------------------------------------------------------
# pdf
# ---------------------------------------------------------------------------


def _build_blank_pdf_bytes() -> bytes:
    """A structurally valid PDF with one page and no text layer at all --
    the shape a scanned document produces."""
    import pypdf

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_pdf_with_no_text_layer_raises_no_readable_text_with_ac022_message():
    content = _build_blank_pdf_bytes()
    with pytest.raises(NoReadableText) as excinfo:
        extract_text("pdf", content)
    # This exact wording is the contract AC-022 depends on downstream in
    # the ingestion service -- assert it verbatim, not just the type.
    assert str(excinfo.value) == _SCANNED_PDF_MESSAGE


def test_pdf_with_text_layer_returns_joined_page_text(monkeypatch):
    import pypdf

    class _FakePage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class _FakeReader:
        def __init__(self, stream):
            self.pages = [_FakePage("Page one."), _FakePage("Page two.")]

    monkeypatch.setattr(pypdf, "PdfReader", _FakeReader)

    result = extract_text("pdf", b"irrelevant-bytes-for-this-double")
    assert result == "Page one.\nPage two."


def test_pdf_parse_failure_raises_extraction_error_not_crash(monkeypatch):
    import pypdf

    class _BrokenReader:
        def __init__(self, stream):
            raise ValueError("not a real PDF stream")

    monkeypatch.setattr(pypdf, "PdfReader", _BrokenReader)

    with pytest.raises(ExtractionError):
        extract_text("pdf", b"garbage")


# ---------------------------------------------------------------------------
# docx
# ---------------------------------------------------------------------------


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    from docx import Document as DocxDocument

    doc = DocxDocument()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_docx_with_paragraphs_returns_joined_text():
    content = _build_docx_bytes(["First paragraph.", "Second paragraph."])
    assert extract_text("docx", content) == "First paragraph.\nSecond paragraph."


def test_docx_with_only_blank_paragraphs_raises_no_readable_text():
    content = _build_docx_bytes(["   ", ""])
    with pytest.raises(NoReadableText):
        extract_text("docx", content)


def test_docx_corrupt_bytes_raise_extraction_error_not_crash():
    # Not a zip/OPC package at all -- python-docx cannot open it.
    with pytest.raises(ExtractionError):
        extract_text("docx", b"this is not a docx file")
