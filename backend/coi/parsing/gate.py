"""Quality gate without a reference (poc-1-ocr/research/gate-design.md), minimal version.

text(): after Kreuzberg / Tesseract (G1 garbage, G2 Polish, G3 form marks, OCR confidence).
vlm():  after a VLM page, against the Tesseract witness (M1 complete, M3 coverage of witness words, M5 capitalised headings kept).
Thresholds live in ladder.json["gate"].
"""
import re

WORD = re.compile(r"[^\W\d_]+")
ALLOWED_PUNCT = set(" \t\n.,;:…_*()/\\-–—„”\"'?!%§|☐#[]^&+=<>@°«»")
MOJIBAKE = re.compile(r"Ã.|Å.|Ä.|�")
PL = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
VOWELS = set("aeiouyąęóAEIOUYĄĘÓ")
LABEL = re.compile(r"(?m)^[^\W\d][^:\n]{1,40}:")


def _nonsense(w: str) -> bool:
    return len(w) >= 3 and (re.search(r"(.)\1\1", w, re.I) is not None or not VOWELS & set(w))


def text(t: str, cfg: dict, confidence: float | None = None, need_marks: bool = True) -> dict:
    """confidence is given for OCR text only. There "label:" lines do not count as marks:
    Tesseract keeps the labels but silently drops the dot leaders next to them (PoC-1)."""
    chars = [c for c in t if not c.isspace()]
    words = WORD.findall(t)
    letters = sum(len(w) for w in words)
    s = {
        "garbage": round((sum(1 for c in chars if not c.isalnum() and c not in ALLOWED_PUNCT) + len(MOJIBAKE.findall(t))) / max(len(chars), 1), 4),
        "nonsense": round(sum(map(_nonsense, words)) / max(len(words), 1), 4),
        "polish": round(sum(1 for c in t if c in PL) / max(letters, 1), 4),
        "marks": t.count("___") + t.count("☐") + (len(LABEL.findall(t)) if confidence is None else 0),
        "confidence": None if confidence is None else round(confidence, 3),
    }
    fails = []
    if s["garbage"] > cfg["max_garbage"]:
        fails.append("G1 garbage")
    if s["nonsense"] > cfg["max_nonsense"]:
        fails.append("G1 nonsense words")
    if letters >= 200 and s["polish"] < cfg["min_polish"]:
        fails.append("G2 no Polish diacritics")
    if need_marks and s["marks"] < cfg["min_marks"]:
        fails.append("G3 no form fields")
    if confidence is not None and confidence < cfg["min_ocr_confidence"]:
        fails.append("OCR confidence")
    return {"ok": not fails, "fails": fails, "signals": s}


def _vocab(t: str) -> set[str]:
    return {w.lower() for w in WORD.findall(t) if len(w) >= 4 and not _nonsense(w)}


def vlm(md: str, finish: str | None, witness: str, cfg: dict) -> dict:
    wit = _vocab(witness)
    coverage = len(wit & _vocab(md)) / len(wit) if wit else 1.0
    # section headings are printed in capitals; a VLM that rewrites them in sentence case loses flow signals
    caps = {w for w in WORD.findall(witness) if len(w) >= 4 and w.isupper() and not _nonsense(w)}
    caps_cov = len(caps & set(WORD.findall(md))) / len(caps) if caps else 1.0
    fails = []
    if finish == "length" or not md.strip():
        fails.append("M1 incomplete")
    if coverage < cfg["min_witness_coverage"]:
        fails.append("M3 misses witness text")
    if caps_cov < cfg["min_witness_coverage"]:
        fails.append("M5 misses capitalised headings")
    return {"ok": not fails, "fails": fails,
            "signals": {"witness_coverage": round(coverage, 3), "witness_words": len(wit), "caps_coverage": round(caps_cov, 3)}}
