"""Unit tests for backend/app/services/document_service.py.

Covers content-sniffed validation (AC-015, AC-017): files are classified by
their actual bytes, not by filename extension, so a renamed spreadsheet or
image is rejected and a plain-text file is accepted regardless of its
extension.
"""

import zipfile
from io import BytesIO

import pytest

from app.services.document_service import (
    SUPPORTED_TYPES_MESSAGE,
    UnsupportedFileType,
    sniff_file_type,
)


def _zip_bytes(names_and_contents: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in names_and_contents.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _docx_bytes() -> bytes:
    return _zip_bytes(
        {
            "word/document.xml": b"<w:document></w:document>",
            "[Content_Types].xml": b"<Types></Types>",
        }
    )


def _xlsx_bytes() -> bytes:
    return _zip_bytes(
        {
            "xl/workbook.xml": b"<workbook></workbook>",
            "[Content_Types].xml": b"<Types></Types>",
        }
    )


class TestSniffFileTypePdf:
    def test_pdf_magic_bytes_detected_regardless_of_extension(self):
        content = b"%PDF-1.4\n%some binary stuff\n"
        assert sniff_file_type("report.PDF", content) == "pdf"
        assert sniff_file_type("renamed.txt", content) == "pdf"


class TestSniffFileTypeDocx:
    def test_valid_docx_zip_detected_as_docx(self):
        content = _docx_bytes()
        assert sniff_file_type("letter.docx", content) == "docx"

    def test_docx_detected_even_with_wrong_extension(self):
        # Content sniffing, not extension, is authoritative: a .docx file
        # renamed to .pdf is still identified by its actual zip contents.
        content = _docx_bytes()
        assert sniff_file_type("letter.pdf", content) == "docx"

    def test_xlsx_zip_without_word_document_part_is_rejected(self):
        # An .xlsx renamed to .docx is still a zip archive, but lacks the
        # word/document.xml part, so it must be rejected rather than
        # misidentified as a Word document.
        content = _xlsx_bytes()
        with pytest.raises(UnsupportedFileType) as excinfo:
            sniff_file_type("spreadsheet.docx", content)
        assert str(excinfo.value) == SUPPORTED_TYPES_MESSAGE

    def test_malformed_zip_with_docx_extension_is_rejected(self):
        content = b"PK\x03\x04" + b"not actually a valid zip archive"
        with pytest.raises(UnsupportedFileType) as excinfo:
            sniff_file_type("broken.docx", content)
        assert str(excinfo.value) == SUPPORTED_TYPES_MESSAGE


class TestSniffFileTypeTextual:
    def test_md_extension_with_text_content_detected_as_md(self):
        content = b"# Heading\n\nSome markdown body text.\n"
        assert sniff_file_type("notes.md", content) == "md"

    def test_md_extension_is_case_insensitive(self):
        content = b"# Heading\n"
        assert sniff_file_type("NOTES.MD", content) == "md"

    def test_txt_extension_with_text_content_detected_as_txt(self):
        content = b"Just some plain text content.\n"
        assert sniff_file_type("notes.txt", content) == "txt"

    def test_text_content_with_unknown_extension_defaults_to_txt(self):
        # Plain text is accepted on its content whatever extension it
        # carries; anything that isn't specifically ".md" falls back to txt.
        content = b"Plain text with no recognizable extension.\n"
        assert sniff_file_type("notes.unknown", content) == "txt"

    def test_text_content_with_no_extension_defaults_to_txt(self):
        content = b"Plain text, no extension at all.\n"
        assert sniff_file_type("README", content) == "txt"

    def test_empty_content_decodes_as_text_and_is_accepted(self):
        # An empty byte string has no null bytes and decodes as UTF-8
        # trivially, so it is treated as (empty) text, not rejected.
        assert sniff_file_type("empty.txt", b"") == "txt"
        assert sniff_file_type("empty.md", b"") == "md"


class TestSniffFileTypeRejection:
    def test_binary_content_with_null_bytes_is_rejected(self):
        content = b"\x00\x01\x02binary garbage\xff\xfe"
        with pytest.raises(UnsupportedFileType) as excinfo:
            sniff_file_type("image.pdf", content)
        assert str(excinfo.value) == SUPPORTED_TYPES_MESSAGE

    def test_non_utf8_content_is_rejected(self):
        # Invalid UTF-8 bytes with no null byte, e.g. a lone continuation
        # byte, should still fail the text sniff.
        content = b"\x80\x81not valid utf-8 at all"
        with pytest.raises(UnsupportedFileType):
            sniff_file_type("mystery.pdf", content)

    def test_renamed_image_disguised_as_pdf_is_rejected(self):
        # A PNG magic-byte header renamed to end in .pdf must still be
        # rejected: the extension is not trusted, only the content is.
        content = b"\x89PNG\r\n\x1a\n" + b"rest of png binary data"
        with pytest.raises(UnsupportedFileType) as excinfo:
            sniff_file_type("photo.pdf", content)
        assert str(excinfo.value) == SUPPORTED_TYPES_MESSAGE
