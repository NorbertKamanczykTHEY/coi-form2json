"""T0 for files with text: Kreuzberg in process (docx, doc, ods, xlsx, PDF text layer)."""
import html
import importlib.metadata
import io
import re
import zipfile

from kreuzberg import ExtractionConfig, MissingDependencyError, OCRError, PageConfig, PluginError, extract_bytes_sync

from ..detect import ParserEnvironmentError
from ..normalize import normalize

NAME = "kreuzberg"
VERSION = importlib.metadata.version("kreuzberg")
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
NOTE = re.compile(r"<w:(footnote|endnote)\b([^>]*)>(.*?)</w:\1>", re.S)


def _clean(md: str) -> str:
    """Kreuzberg markdown -> plain lines: its headings/bold are font guesses, headings come from our own patterns."""
    md = html.unescape(md).replace("\t", " ")
    md = re.sub(r"\[\^\d+\]", "", md)  # footnote refs
    md = re.sub(r"\\([\\`*_{}\[\]()#+\-.!=<>~^])", r"\1", md)  # markdown escapes
    md = re.sub(r"\^([^^\n]*)\^", r"\1", md)  # ^1)^ superscript
    md = re.sub(r"(?m)^#{1,6}\s+", "", md)
    md = md.replace("**", "")
    return re.sub(r"[  ]{2,}", " ", md)


def _docx_notes(data: bytes) -> list[str]:
    """Word footnotes/endnotes: no Kreuzberg output mode includes them, yet "*Numer PESEL wpisują…" drives the flow."""
    notes = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for part in ("word/footnotes.xml", "word/endnotes.xml"):
            if part not in z.namelist():
                continue
            for _, attrs, body in NOTE.findall(z.read(part).decode("utf-8", "replace")):
                if "w:type=" in attrs:  # separator / continuationSeparator
                    continue
                text = html.unescape("".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", body))).strip()
                if text:  # custom marks ("*") are in the text; numbered ones get their number back
                    notes.append(text if text[0] in "*" or text[0].isdigit() else f"{len(notes) + 1}) {text}")
    return notes


def native(data: bytes, mime: str) -> list[str]:
    """One normalized text per page (office formats have no pages: one entry)."""
    cfg = ExtractionConfig(output_format="markdown", disable_ocr=True, pages=PageConfig(extract_pages=True))
    try:
        r = extract_bytes_sync(data, mime, cfg)
    except (MissingDependencyError, PluginError, OCRError) as e:  # install problem; ParsingError (broken file) propagates as is
        raise ParserEnvironmentError(f"kreuzberg: {e}") from e
    texts = [p["content"] for p in r.pages] if mime == "application/pdf" and r.pages else [r.content]
    if mime == DOCX and (notes := _docx_notes(data)):
        texts[-1] += "\n\n" + "\n\n".join(notes)
    return [normalize(_clean(t)) for t in texts]
