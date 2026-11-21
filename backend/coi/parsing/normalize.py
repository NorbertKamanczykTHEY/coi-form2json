"""Marker normalisation: every checkbox becomes ☐, every fill-in place becomes ___ (spec, table "Normalizacja")."""
import re

# Wingdings/Symbol boxes from Word arrive as private-use code points (U+F071 = ❑, U+F06F/F0A8 = □, U+F0FE = ☑)
BOX = re.compile(r"[❑□▢◻⬜❒☐\uf06f\uf070\uf071\uf072\uf0a8\uf0fe]")
# dot leaders, ellipses, underscores (>= 4 chars), spaced dots ". . . .", VLM "[___]"
LEADER = re.compile(r"\[_+\]|[.…_·](?:\s?[.…_·]){3,}|…{2,}")
# Tesseract reads a box at the start of a choice as "U" or "Q" (followed by a lowercase word)
OCR_BOX = re.compile(r"(?m)(^|\s{2,}|\|\s*)[UQ](?=\s+\w*[a-ząćęłńóśźż])")


def normalize(text: str, ocr: bool = False) -> str:
    text = BOX.sub("☐", text)
    if ocr:
        text = OCR_BOX.sub(r"\1☐", text)
    text = LEADER.sub("___", text)
    return re.sub(r"(?:___\s*){2,}", "___ ", text)  # adjacent leaders -> one place to fill in
