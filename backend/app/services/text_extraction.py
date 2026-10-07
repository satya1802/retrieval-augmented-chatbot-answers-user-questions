"""Extract plain text from a supported document's raw bytes.

Only the four types `document_service.sniff_file_type` recognises are
handled here: pdf, docx, md, txt. No OCR dependency (constraint) -- a PDF
whose pages carry no text layer raises `NoReadableText`, which the ingestion
service turns into the exact AC-022 failure message, not a crash.
"""

from __future__ import annotations

import io


class ExtractionError(Exception):
    """The file could not be parsed at all (corrupt, unreadable, etc.)."""


class NoReadableText(Exception):
    """The file parsed structurally but contains no extractable text -- the
    scanned-PDF case AC-022 names explicitly."""


_SCANNED_PDF_MESSAGE = (
    "No readable text was found in this PDF. Scanned documents requiring "
    "OCR are not supported in this version."
)


def extract_text(file_type: str, content: bytes) -> str:
    """Return the document's text, or raise `NoReadableText` /
    `ExtractionError`. `file_type` is one of "pdf", "docx", "md", "txt"."""
    if file_type in ("txt", "md"):
        return _extract_plain_text(content)
    if file_type == "pdf":
        return _extract_pdf(content)
    if file_type == "docx":
        return _extract_docx(content)
    raise ExtractionError(f"unsupported file type: {file_type}")


def _extract_plain_text(content: bytes) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError("file is not valid UTF-8 text") from exc
    if not text.strip():
        raise NoReadableText("No readable text was found in this document.")
    return text


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - pypdf ships in requirements.txt
        raise ExtractionError("PDF extraction is unavailable") from exc

    try:
        reader = PdfReader(io.BytesIO(content))
        pages_text = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ExtractionError(f"could not parse PDF: {exc}") from exc

    text = "\n".join(pages_text).strip()
    if not text:
        raise NoReadableText(_SCANNED_PDF_MESSAGE)
    return text


def _extract_docx(content: bytes) -> str:
    try:
        from docx import Document as DocxDocument
    except ImportError as exc:  # pragma: no cover - python-docx ships in requirements.txt
        raise ExtractionError("DOCX extraction is unavailable") from exc

    try:
        doc = DocxDocument(io.BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs).strip()
    except Exception as exc:
        raise ExtractionError(f"could not parse DOCX: {exc}") from exc

    if not text:
        raise NoReadableText("No readable text was found in this document.")
    return text
