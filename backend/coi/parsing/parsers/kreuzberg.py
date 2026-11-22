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


def _wt(xml: str) -> str:
    return html.unescape("".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml.replace("<w:tab/>", "<w:t> </w:t>")))).strip()


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
                text = _wt(body)
                if text:  # custom marks ("*") are in the text; numbered ones get their number back
                    notes.append(text if text[0] in "*" or text[0].isdigit() else f"{len(notes) + 1}) {text}")
    return notes


def _docx_margins(data: bytes, seen: str) -> tuple[list[str], list[str]]:
    """Headers, footers, comments and text boxes (#7: "Opłata skarbowa – 82 zł" sits in footer2.xml).
    Paragraphs already in the main text (Kreuzberg reads some text boxes) or in another part (header1/2/3) are skipped.
    shortcut: text-box paragraphs go to the end, their position on the page is not read; place them if a form needs it."""
    key = lambda t: re.sub(r"\W+", "", t).lower()  # noqa: E731
    known = key(seen)
    top, bottom, done = [], [], set()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = sorted(z.namelist())
        parts = [n for n in names if re.fullmatch(r"word/header\d*\.xml", n)] + \
                [n for n in names if re.fullmatch(r"word/(footer\d*|comments|document)\.xml", n)]
        for part in parts:
            xml = z.read(part).decode("utf-8", "replace")
            if part == "word/document.xml":  # only what sits in text boxes
                xml = "".join(re.findall(r"<w:txbxContent>(.*?)</w:txbxContent>", xml, re.S))
            for para in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
                text = _wt(para)
                k = key(text)
                if len(k) < 3 or k in done or k in known:  # page numbers, repeats, already extracted
                    continue
                done.add(k)
                (top if "header" in part else bottom).append(text)
    return top, bottom


def native(data: bytes, mime: str) -> list[str]:
    """One normalized text per page (office formats have no pages: one entry)."""
    cfg = ExtractionConfig(output_format="markdown", disable_ocr=True, pages=PageConfig(extract_pages=True))
    try:
        r = extract_bytes_sync(data, mime, cfg)
    except (MissingDependencyError, PluginError, OCRError) as e:  # install problem; ParsingError (broken file) propagates as is
        raise ParserEnvironmentError(f"kreuzberg: {e}") from e
    texts = [p["content"] for p in r.pages] if mime == "application/pdf" and r.pages else [r.content]
    if mime == DOCX:
        top, bottom = _docx_margins(data, texts[-1])
        texts[-1] = "\n\n".join(top + [texts[-1]] + bottom + _docx_notes(data))
    return [normalize(_clean(t)) for t in texts]
