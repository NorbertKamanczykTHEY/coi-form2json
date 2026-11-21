"""File type: allowed extension (case-insensitive) + magic bytes must agree. DOC category = .doc|.docx either way."""
from pathlib import PurePath

import filetype
from kreuzberg import ExtractionConfig, KreuzbergError, PageConfig, extract_bytes_sync

from .model import Kind


class UnsupportedType(ValueError):
    """-> HTTP 415"""


class TooLarge(ValueError):
    """-> HTTP 413"""


# extension -> magic-bytes types it may contain (filetype names jpeg "jpg")
ALLOWED = {
    "pdf": {"pdf"},
    "doc": {"doc", "docx"},
    "docx": {"doc", "docx"},
    "ods": {"ods"},
    "xlsx": {"xlsx"},
    "jpg": {"jpg"},
    "jpeg": {"jpg"},
    "png": {"png"},
}
KIND = {"doc": Kind.DOC, "docx": Kind.DOCX, "ods": Kind.ODS, "xlsx": Kind.XLSX, "jpg": Kind.IMAGE, "png": Kind.IMAGE}


def pdf_page_chars(data: bytes) -> list[int]:
    r = extract_bytes_sync(data, "application/pdf", ExtractionConfig(disable_ocr=True, pages=PageConfig(extract_pages=True)))
    return [len(p["content"].strip()) for p in r.pages or []]


def detect(data: bytes, filename: str, max_mb: float, pdf_min_chars: int = 50) -> tuple[Kind, str]:
    """-> (kind, mime). Raises TooLarge / UnsupportedType."""
    if len(data) > max_mb * 1024 * 1024:
        raise TooLarge(f"file is {len(data) / 2**20:.1f} MB, limit {max_mb} MB")
    ext = PurePath(filename).suffix.lower().lstrip(".")
    if ext not in ALLOWED:
        raise UnsupportedType(f"extension .{ext} not allowed")
    sniff = filetype.guess(data)
    if sniff is None or sniff.extension not in ALLOWED[ext]:
        raise UnsupportedType(f"content ({sniff.mime if sniff else 'unknown'}) does not match .{ext}")
    if sniff.extension != "pdf":
        return KIND[sniff.extension], sniff.mime
    try:
        chars = pdf_page_chars(data)
    except KreuzbergError as e:
        raise UnsupportedType(f"unreadable PDF: {e}") from e
    if not chars:
        raise UnsupportedType("PDF has no pages")
    # file-level kind; the pipeline still routes each page by its own text layer
    return (Kind.PDF_TEXT if min(chars) >= pdf_min_chars else Kind.PDF_SCAN), sniff.mime
