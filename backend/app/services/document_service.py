"""Content-sniffed validation for uploaded documents (AC-015, AC-017).

Validation goes by sniffed bytes, not filename extension alone: a
spreadsheet or image renamed to end in `.pdf` is still rejected, and a
plain-text file is accepted on its content whatever extension it carries.
"""

import io
import zipfile

SUPPORTED_TYPES_MESSAGE = (
    "Supported file types: PDF (.pdf), Word (.docx), Markdown (.md) and plain text (.txt)."
)


class UnsupportedFileType(Exception):
    """Raised when a file's sniffed content is not one of the supported types."""


def _looks_like_text(content: bytes) -> bool:
    if b"\x00" in content:
        return False
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def sniff_file_type(filename: str, content: bytes) -> str:
    """Return "pdf" | "docx" | "md" | "txt", or raise UnsupportedFileType.

    PDF and DOCX are identified by magic bytes (and, for DOCX, by the zip
    archive actually containing a Word document part -- an .xlsx is also a
    zip, but is rejected here because it lacks `word/document.xml`).
    Markdown and plain text share no distinct magic number, so content that
    merely decodes as UTF-8 text is accepted and labeled from its extension.
    """
    if content.startswith(b"%PDF-"):
        return "pdf"

    if content[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile as exc:
            raise UnsupportedFileType(SUPPORTED_TYPES_MESSAGE) from exc
        if "word/document.xml" in names:
            return "docx"
        raise UnsupportedFileType(SUPPORTED_TYPES_MESSAGE)

    if _looks_like_text(content):
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return "md" if extension == "md" else "txt"

    raise UnsupportedFileType(SUPPORTED_TYPES_MESSAGE)
