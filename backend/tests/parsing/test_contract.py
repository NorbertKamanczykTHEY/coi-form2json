"""Contract tests on every format of forms #1 and #7. Image paths may escalate to the VLM: marked `eden`."""
import io
import json
import re
import unicodedata

import pytest
from PIL import Image

from coi.parsing import ParsedDocument, parse, to_markdown
from coi.parsing.parsers.vision import split_pages

from .conftest import FILES, GOLD

LEADER = re.compile(r"___")
NATIVE = {".doc", ".docx", ".ods", ".xlsx", ".pdf"}
SHEETS = {".ods", ".xlsx"}  # the spreadsheet versions have no dot leaders and no box glyphs in the source


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"\s+", " ", re.sub(r"[*#|`>]", " ", s)).strip()


def check(doc: ParsedDocument, form: str, ext: str):
    # structure
    d = json.loads(json.dumps(doc.to_dict(), ensure_ascii=False))
    assert set(d) == {"source", "pages", "warnings", "trace"}
    assert {"filename", "kind", "mime", "parser", "parser_version", "seconds"} <= set(d["source"])
    assert [p["number"] for p in d["pages"]] == list(range(1, len(d["pages"]) + 1))
    blocks = [b for p in doc.pages for b in p.blocks]
    assert blocks, doc.warnings
    for b in blocks:
        assert b.kind in ("heading", "paragraph", "list_item", "table", "footnote")
        assert (b.level in (1, 2)) if b.kind == "heading" else b.level is None
        assert (b.rows is not None) == (b.kind == "table")
    if ext != ".doc":  # Kreuzberg reads legacy Word 97 as run-on paragraphs: the title is glued to the next sentence
        assert any(b.kind == "heading" for b in blocks)

    text = doc.text
    md = to_markdown(doc)
    # markers: never raw glyphs or dot runs, normalized ones where the source has them
    assert not re.search(r"[❑□▢\uf071]|\.{6,}|…{3,}", md)
    gold = GOLD[form]
    if ext not in SHEETS:
        assert len(LEADER.findall(text)) >= 3
        if gold.get("options"):
            assert text.count("☐") >= 2

    # control phrases (exact, diacritics-sensitive) and field labels
    t = _norm(text)
    anchors = [a for a in gold["anchors"] if _norm(a) in t]
    assert len(anchors) / len(gold["anchors"]) >= 0.75, (set(gold["anchors"]) - set(anchors))
    low = t.lower()
    missing = [f["id"] for f in gold["fields"] if not any(a.lower() in low for a in f["aliases"])]
    assert len(missing) <= 1, missing


@pytest.mark.parametrize("form,path", [f for f in FILES if f[1].suffix.lower() in NATIVE], ids=lambda x: getattr(x, "name", x))
def test_native(form, path):
    doc = parse(path.read_bytes(), path.name)
    check(doc, form, path.suffix.lower())
    assert doc.source["cost"] == 0


@pytest.mark.eden
@pytest.mark.parametrize("form,path", [f for f in FILES if f[1].suffix.lower() in (".png", ".jpg", ".jpeg")], ids=lambda x: getattr(x, "name", x))
def test_image(form, path):
    doc = parse(path.read_bytes(), path.name)
    print(path.suffix, doc.source, [(e["page"], e["step"], e.get("model"), e.get("accepted")) for e in doc.trace])
    check(doc, form, path.suffix.lower())


@pytest.mark.eden
def test_scanned_pdf(form1_jpg):
    # the jpg is two A4 pages stitched together: make a realistic 2-page scan
    first, *rest = split_pages(Image.open(form1_jpg))
    buf = io.BytesIO()
    first.save(buf, "PDF", save_all=True, append_images=rest, resolution=200)
    doc = parse(buf.getvalue(), "skan.pdf")
    print(doc.source, [(e["page"], e["step"], e.get("model"), e.get("accepted")) for e in doc.trace])
    assert doc.source["kind"] == "pdf_scan"
    assert len(doc.pages) == 2 and all(e["step"] != "T0" or e["parser"] == "tesseract" for e in doc.trace)
    check(doc, "form1", ".pdf")
