"""Contract tests on every format of forms #1 and #7. Image paths may escalate to the VLM: marked `eden`."""
import io
import json
import re
import unicodedata
from pathlib import Path

import pytest
from PIL import Image

from coi.parsing import ParsedDocument, parse, to_markdown
from coi.parsing.parsers.vision import split_pages

from .conftest import FILES, GOLD, form_files

LEADER = re.compile(r"___")
NATIVE = {".doc", ".docx", ".ods", ".xlsx", ".pdf"}


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
    # spreadsheets too: their lines and boxes come from cell borders (parsers/sheet.py)
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


@pytest.mark.parametrize("ext", [".docx", ".DOC"])
def test_docx_footnotes_kept(ext):
    """#5: '*Numer PESEL wpisują…' lives in word/footnotes.xml (the .DOC is OOXML too)."""
    path = next(p for p in form_files("5. ") if p.suffix == ext)
    doc = parse(path.read_bytes(), path.name)
    notes = [b.text for p in doc.pages for b in p.blocks if b.kind == "footnote"]
    assert any(n.startswith("*Numer PESEL wpisują") for n in notes), notes
    assert not any("G5" in w for w in doc.warnings)


def test_star_without_footnote_escalates():
    from coi.parsing import gate
    cfg = json.loads((Path(gate.__file__).parent / "ladder.json").read_text())["gate"]
    assert "G5 * without footnote" in gate.text("PESEL* ___ ___ ___", cfg)["fails"]
    assert gate.text("PESEL* ___ ___ ___\n*Numer PESEL wpisują podatnicy", cfg)["ok"]


def test_sheet_borders_become_markers():
    path = next(p for p in form_files("7. ") if p.suffix == ".ODS")
    lines = parse(path.read_bytes(), path.name).text.splitlines()
    assert "Płeć: ☐ pies ☐ suka" in lines
    assert "Rasa psa: ___" in lines and "Wrocław, dnia ___" in lines
    xlsx = next(p for p in form_files("1. ") if p.suffix == ".xlsx")
    assert "w miejscowości ___ przy ulicy1) ___" in parse(xlsx.read_bytes(), xlsx.name).text.splitlines()


def test_broken_sheet_is_a_file_error():
    with pytest.raises(ValueError):
        from coi.parsing.parsers import sheet
        sheet.read(b"PK\x03\x04 not a zip", "ods")
