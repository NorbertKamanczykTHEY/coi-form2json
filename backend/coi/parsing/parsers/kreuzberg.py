"""T0: Kreuzberg in process. Native text for office/PDF, Tesseract `pol` for page images (also the witness for the VLM gate)."""
import html
import importlib.metadata
import re

from kreuzberg import ExtractionConfig, OcrConfig, PageConfig, extract_bytes_sync

from ..normalize import normalize

NAME = "kreuzberg"
VERSION = importlib.metadata.version("kreuzberg")
OCR = OcrConfig(backend="tesseract", language="pol")


def _clean(md: str) -> str:
    """Kreuzberg markdown -> plain lines: its headings/bold are font guesses, headings come from our own patterns."""
    md = html.unescape(md).replace("\t", " ")
    md = re.sub(r"\[\^\d+\]", "", md)  # footnote refs
    md = re.sub(r"\\([\\`*_{}\[\]()#+\-.!=<>~^])", r"\1", md)  # markdown escapes
    md = re.sub(r"\^([^^\n]*)\^", r"\1", md)  # ^1)^ superscript
    md = re.sub(r"(?m)^#{1,6}\s+", "", md)
    md = md.replace("**", "")
    return re.sub(r"[  ]{2,}", " ", md)


def native(data: bytes, mime: str) -> list[str]:
    """One normalized text per page (office formats have no pages: one entry)."""
    cfg = ExtractionConfig(output_format="markdown", disable_ocr=True, pages=PageConfig(extract_pages=True))
    r = extract_bytes_sync(data, mime, cfg)
    texts = [p["content"] for p in r.pages] if mime == "application/pdf" and r.pages else [r.content]
    return [normalize(_clean(t)) for t in texts]


def ocr(image: bytes, mime: str = "image/png") -> tuple[str, float | None]:
    """Tesseract text (normalized, ocr=True) + mean word confidence."""
    r = extract_bytes_sync(image, mime, ExtractionConfig(output_format="plain", ocr=OCR))
    conf = [e["confidence"]["recognition"] for e in r.ocr_elements or [] if e.get("level") == "word" and e["text"].strip()]
    return normalize(r.content, ocr=True), (sum(conf) / len(conf) if conf else None)
