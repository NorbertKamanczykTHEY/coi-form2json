import io

import pytest
from PIL import Image

from coi.parsing.detect import TooLarge, UnsupportedType, detect
from coi.parsing.model import Kind
from coi.parsing.normalize import normalize

from .conftest import FILES

EXPECTED = {".doc": Kind.DOC, ".docx": Kind.DOCX, ".ods": Kind.ODS, ".xlsx": Kind.XLSX, ".pdf": Kind.PDF_TEXT,
            ".png": Kind.IMAGE, ".jpg": Kind.IMAGE, ".jpeg": Kind.IMAGE}


@pytest.mark.parametrize("form,path", FILES, ids=lambda x: x.name if hasattr(x, "name") else x)
def test_kind_of_every_material(form, path):
    ext = path.suffix.lower()
    if ext == ".jpe":
        with pytest.raises(UnsupportedType):
            detect(path.read_bytes(), path.name, 50)
        return
    kind, _ = detect(path.read_bytes(), path.name, 50)
    # form7 .DOC is OOXML inside: accepted, parsed as docx
    assert kind == (Kind.DOCX if path.suffix == ".DOC" else EXPECTED[ext])


def test_scanned_pdf_is_pdf_scan(form1_jpg):
    buf = io.BytesIO()
    Image.open(form1_jpg).convert("RGB").save(buf, "PDF")
    assert detect(buf.getvalue(), "skan.PDF", 50)[0] == Kind.PDF_SCAN


@pytest.mark.parametrize("data,name", [
    (b"\x89PNG\r\n\x1a\n" + b"\0" * 64, "wniosek.pdf"),  # png content, pdf extension
    (b"%PDF-1.4\n", "wniosek.png"),
    (b"hello", "wniosek.docx"),
    (b"%PDF-1.4\n", "wniosek.txt"),
    (b"%PDF-1.4\n", "wniosek"),
])
def test_rejects_mismatch(data, name):
    with pytest.raises(UnsupportedType):
        detect(data, name, 50)


def test_too_large():
    with pytest.raises(TooLarge):
        detect(b"%PDF" + b"0" * 2_000_000, "a.pdf", 1)


@pytest.mark.parametrize("raw,out", [
    ("Wrocław, dnia ..................................", "Wrocław, dnia ___"),
    ("adres: ………………………………….", "adres: ___"),
    ("nr ____ przy . . . . ulicy", "nr ___ przy ___ ulicy"),
    ("❑ pies \uf071 suka □ x", "☐ pies ☐ suka ☐ x"),
    ("Imię: [___]", "Imię: ___"),
    ("koniec zdania... i dalej", "koniec zdania... i dalej"),
])
def test_normalize(raw, out):
    assert normalize(raw) == out


def test_normalize_tesseract_boxes():
    assert normalize("Płeć: Q pies U suka", ocr=True) == "Płeć: Q pies U suka"  # single space: too ambiguous
    assert normalize("Q pies\nU suka", ocr=True) == "☐ pies\n☐ suka"
