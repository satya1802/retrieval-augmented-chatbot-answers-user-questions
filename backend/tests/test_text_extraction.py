"""Unit tests for app/services/text_extraction.py.

No AC numbers are attached directly to this module, but its docstring and
`ingestion_service`'s usage of it name the contract this exercises: for each
of the four types `document_service.sniff_file_type` can hand it (pdf,
docx, md, txt), `extract_text` either returns the document's text, raises
`NoReadableText` when the file parses but carries nothing extractable (the
scanned-PDF case named by AC-022), or raises `ExtractionError` when the file
cannot be parsed at all. `ingestion_service` relies on exactly that
three-way split to decide between a "ready" document, a scanned-PDF
failure message, and a generic extraction failure message -- so the message
text asserted here for the scanned-PDF case is pinned to the exact string
`ingestion_service.SCANNED_PDF_MESSAGE` surfaces to the user, not just to
some string containing "scanned".

PDF and DOCX fixtures are built in-code rather than checked in as binary
blobs: the PDF helper hand-assembles a minimal, correctly cross-referenced
single-page document so pypdf parses it without falling back to recovery
mode, and the DOCX helper drives `python-docx` itself (the same library the
module under test uses) to produce a real, valid archive.
"""

from __future__ import annotations

import io

import pytest

from app.services.ingestion_service import SCANNED_PDF_MESSAGE as INGESTION_SCANNED_PDF_MESSAGE
from app.services.text_extraction import (
    ExtractionError,
    NoReadableText,
    extract_text,
)


def _make_pdf(text: str) -> bytes:
    """Build a minimal, valid single-page PDF whose content stream renders
    `text` (or nothing, if `text` is empty), with a correctly-offset xref
    table so pypdf parses it on the normal path."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            b"/Resources << /Font << /F1 4 0 R >> >> "
            b"/MediaBox [0 0 612 792] /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream_body = f"BT /F1 24 Tf 72 712 Td ({text}) Tj ET".encode()
    objects.append(
        b"<< /Length " + str(len(stream_body)).encode() + b" >>\nstream\n"
        + stream_body
        + b"\nendstream"
    )

    body = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_offset = len(body)
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        xref += f"{offset:010d} 00000 n \n".encode()

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()

    return body + xref + trailer


def _make_docx(paragraphs: list[str]) -> bytes:
    from docx import Document as DocxDocument

    doc = DocxDocument()
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# --------------------------------------------------------------- txt / md --


class TestPlainTextAndMarkdown:
    def test_txt_returns_decoded_text(self):
        assert extract_text("txt", b"hello world") == "hello world"

    def test_md_returns_decoded_text_unmodified(self):
        content = "# Heading\n\nSome body text.".encode("utf-8")
        assert extract_text("md", content) == "# Heading\n\nSome body text."

    def test_txt_preserves_non_ascii_utf8_content(self):
        content = "café élève 中文".encode("utf-8")
        assert extract_text("txt", content) == content.decode("utf-8")

    def test_empty_txt_raises_no_readable_text(self):
        with pytest.raises(NoReadableText):
            extract_text("txt", b"")

    def test_whitespace_only_md_raises_no_readable_text(self):
        with pytest.raises(NoReadableText):
            extract_text("md", b"   \n\t  \n")

    def test_non_utf8_txt_raises_extraction_error(self):
        with pytest.raises(ExtractionError):
            extract_text("txt", b"\xff\xfe\x00\x01not valid utf-8")


# --------------------------------------------------------------------- pdf --


class TestPdf:
    def test_pdf_with_a_text_layer_returns_its_text(self):
        content = _make_pdf("Hello World")
        assert extract_text("pdf", content) == "Hello World"

    def test_scanned_pdf_with_no_text_layer_raises_no_readable_text_with_the_ac022_message(self):
        content = _make_pdf("")

        with pytest.raises(NoReadableText) as excinfo:
            extract_text("pdf", content)

        assert str(excinfo.value) == (
            "No readable text was found in this PDF. Scanned documents "
            "requiring OCR are not supported in this version."
        )

    def test_scanned_pdf_message_matches_what_ingestion_service_surfaces(self):
        """ingestion_service catches `NoReadableText` and reports its own
        `SCANNED_PDF_MESSAGE` constant rather than this exception's message
        directly -- the two must stay byte-for-byte identical, or a user
        would see one wording from a direct call and another in the
        product, depending on which layer happened to raise."""
        content = _make_pdf("")

        with pytest.raises(NoReadableText) as excinfo:
            extract_text("pdf", content)

        assert str(excinfo.value) == INGESTION_SCANNED_PDF_MESSAGE

    def test_corrupt_pdf_bytes_raise_extraction_error_not_a_crash(self):
        content = b"%PDF-1.4\nthis is not a parseable pdf body at all\n%%EOF"
        with pytest.raises(ExtractionError):
            extract_text("pdf", content)

    def test_completely_non_pdf_bytes_raise_extraction_error(self):
        with pytest.raises(ExtractionError):
            extract_text("pdf", b"just some random bytes, not a pdf header even")


# -------------------------------------------------------------------- docx --


class TestDocx:
    def test_docx_with_paragraphs_returns_their_text_joined_by_newlines(self):
        content = _make_docx(["First paragraph.", "Second paragraph."])
        assert extract_text("docx", content) == "First paragraph.\nSecond paragraph."

    def test_docx_with_no_paragraphs_raises_no_readable_text(self):
        content = _make_docx([])
        with pytest.raises(NoReadableText):
            extract_text("docx", content)

    def test_docx_with_only_blank_paragraphs_raises_no_readable_text(self):
        content = _make_docx(["", "   "])
        with pytest.raises(NoReadableText):
            extract_text("docx", content)

    def test_corrupt_docx_zip_raises_extraction_error_not_a_crash(self):
        content = b"PK\x03\x04" + b"not actually a valid zip archive at all"
        with pytest.raises(ExtractionError):
            extract_text("docx", content)


# ---------------------------------------------------------- unsupported type


class TestUnsupportedFileType:
    def test_unrecognized_file_type_raises_extraction_error_naming_the_type(self):
        with pytest.raises(ExtractionError) as excinfo:
            extract_text("xlsx", b"irrelevant content")
        assert "xlsx" in str(excinfo.value)
