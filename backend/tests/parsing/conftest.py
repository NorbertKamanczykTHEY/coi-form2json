"""Form files are read in place from materials/ (not copied). Gold phrases come from poc-1-ocr/bench/gold_form*.json."""
import json
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]  # coi_formularze/
MATERIALS = ROOT / "materials"
GOLD = {f: json.loads((ROOT / f"poc-1-ocr/bench/gold_{f}.json").read_text()) for f in ("form1", "form7")}


def form_files(prefix: str) -> list[Path]:
    folder = next(MATERIALS.glob(f"{prefix}*"))
    # macOS stores names in NFD; the "wizualizacja" docx and the JSON are not source forms
    return sorted(p for p in folder.iterdir() if p.suffix.lower() != ".json" and "wizualizacja" not in unicodedata.normalize("NFC", p.name))


FILES = [("form1", p) for p in form_files("1. ")] + [("form7", p) for p in form_files("7. ")]


@pytest.fixture(scope="session")
def form1_jpg() -> Path:
    return next(p for f, p in FILES if f == "form1" and p.suffix == ".jpg")
