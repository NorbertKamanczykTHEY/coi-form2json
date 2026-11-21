"""T0 for files with text: Kreuzberg in process (docx, doc, ods, xlsx, PDF text layer)."""
import html
import importlib.metadata
import re

from kreuzberg import ExtractionConfig, MissingDependencyError, OCRError, PageConfig, PluginError, extract_bytes_sync

from ..detect import ParserEnvironmentError
from ..normalize import normalize

NAME = "kreuzberg"
VERSION = importlib.metadata.version("kreuzberg")


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
    try:
        r = extract_bytes_sync(data, mime, cfg)
    except (MissingDependencyError, PluginError, OCRError) as e:  # install problem; ParsingError (broken file) propagates as is
        raise ParserEnvironmentError(f"kreuzberg: {e}") from e
    texts = [p["content"] for p in r.pages] if mime == "application/pdf" and r.pages else [r.content]
    return [normalize(_clean(t)) for t in texts]
