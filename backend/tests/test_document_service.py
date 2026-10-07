"""Unit tests for app.services.document_service.

Covers content-sniffed validation (AC-015, AC-017): the file's actual bytes
decide its type, not the filename extension -- so a renamed spreadsheet is
still rejected and a plain-text file is accepted whatever extension it
carries.
"""

import io
import zipfile

import pytest

from app.services.document_service import (
    SUPPORTED_TYPES_MESSAGE,
    UnsupportedFileType,
    sniff_file_type,
)


def _zip_bytes(names_to_content: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in names_to_content.items():
            archive.writestr(name, content)
    return buf.getvalue()


def _docx_bytes() -> bytes:
    # Minimal shape of a real .docx: a zip archive containing the Word part.
    return _zip_bytes(
        {
            "[Content_Types].xml": "<Types/>",
            "word/document.xml": "<w:document/>",
        }
    )


def _xlsx_like_bytes() -> bytes:
    # A zip archive that is NOT a Word document -- e.g. an .xlsx renamed
    # to .docx. Must be rejected even though it starts with the zip magic.
    return _zip_bytes(
        {
            "[Content_Types].xml": "<Types/>",
            "xl/workbook.xml": "<workbook/>",
        }
    )


class TestPdf:
    def test_pdf_magic_bytes_detected_as_pdf(self):
        content = b"%PDF-1.4\n%...rest of a real pdf would follow..."
        assert sniff_file_type("report.pdf", content) == "pdf"

    def test_text_renamed_to_pdf_extension_is_not_sniffed_as_pdf(self):
        # Extension lies about the type; content is plain text, so it is
        # accepted on its own merits as text, never mislabeled "pdf".
        content = b"just some plain text, not a pdf"
        assert sniff_file_type("notes.pdf", content) == "txt"


class TestDocx:
    def test_real_docx_bytes_detected_as_docx(self):
        assert sniff_file_type("resume.docx", _docx_bytes()) == "docx"

    def test_spreadsheet_renamed_to_docx_is_rejected(self):
        # A zip file that is a zip but not a Word document (e.g. an .xlsx
        # renamed to end in .docx) must still be rejected -- the ticket's
        # headline scenario for content-over-extension validation.
        with pytest.raises(UnsupportedFileType) as excinfo:
            sniff_file_type("budget.docx", _xlsx_like_bytes())
        assert str(excinfo.value) == SUPPORTED_TYPES_MESSAGE

    def test_corrupt_zip_with_pk_header_is_rejected(self):
        # Starts with the zip magic number but is not a valid archive at
        # all; must raise UnsupportedFileType rather than propagate the
        # underlying BadZipFile.
        content = b"PK\x03\x04" + b"not actually a valid zip stream"
        with pytest.raises(UnsupportedFileType):
            sniff_file_type("broken.docx", content)


class TestTextAndMarkdown:
    def test_md_extension_on_text_content_detected_as_markdown(self):
        content = "# Heading\n\nSome *markdown* body text.".encode("utf-8")
        assert sniff_file_type("README.md", content) == "md"

    def test_txt_extension_on_text_content_detected_as_text(self):
        content = "plain prose, nothing special".encode("utf-8")
        assert sniff_file_type("notes.txt", content) == "txt"

    def test_text_with_no_extension_defaults_to_txt(self):
        content = "no extension at all".encode("utf-8")
        assert sniff_file_type("README", content) == "txt"

    def test_text_with_unrelated_extension_still_detected_as_txt(self):
        # Extension is neither .md nor a recognized binary type; content
        # decodes as text, so it is accepted and labeled "txt" on content
        # alone, exactly as the module's docstring promises.
        content = "some text content".encode("utf-8")
        assert sniff_file_type("data.csv", content) == "txt"

    def test_md_detection_is_case_insensitive_on_extension(self):
        content = "# Title".encode("utf-8")
        assert sniff_file_type("README.MD", content) == "md"

    def test_empty_file_decodes_as_empty_text(self):
        # Documents actual behaviour: empty bytes decode trivially as
        # UTF-8, so an empty .txt upload is accepted, not rejected.
        assert sniff_file_type("empty.txt", b"") == "txt"


class TestRejected:
    def test_binary_garbage_is_rejected(self):
        # Not PDF magic, not a zip, not valid UTF-8 text -- no supported
        # type can be sniffed from it.
        content = bytes([0xFF, 0xFE, 0x00, 0x01, 0x02, 0x80, 0x81])
        with pytest.raises(UnsupportedFileType) as excinfo:
            sniff_file_type("mystery.bin", content)
        assert str(excinfo.value) == SUPPORTED_TYPES_MESSAGE

    def test_content_with_null_byte_is_rejected_even_if_utf8_decodable(self):
        # A null byte marks binary content even when the rest would
        # otherwise decode as UTF-8; _looks_like_text must reject it.
        content = b"hello\x00world"
        with pytest.raises(UnsupportedFileType):
            sniff_file_type("odd.txt", content)

    def test_image_bytes_are_rejected(self):
        # PNG magic number: binary, not zip-based, not valid UTF-8.
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        with pytest.raises(UnsupportedFileType):
            sniff_file_type("photo.png", content)
