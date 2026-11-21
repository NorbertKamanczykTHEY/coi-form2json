"""Spike: run the backend parser on chosen materials, save ParsedDocument JSON + block-anchored markdown.

usage (from app/backend): uv run python ../spikes/field-extraction/parse_inputs.py
"""
import json
import sys
from pathlib import Path

from coi.parsing import parse

M = Path(__file__).resolve().parents[3] / "materials"
OUT = Path(__file__).resolve().parent / "out"
INPUTS = {
    "form1": "1. */Wniosek o ustalenie numeru porządkowego nieruchomości.docx",
    "form5": "5. */Wniosek o stwierdzenie nadpłaty podatku.docx",
    "form3": "3. */Wniosek o wydanie zaświadczenia.docx",
    "form7": "7. */*.DOC",
    "form9": "9. */*.docx",
}


def anchored(doc) -> str:
    """One line per block, prefixed with its anchor p<page>.b<index>: the LLM cites anchors, field_map gets page+block for free."""
    out = []
    for p in doc.pages:
        for i, b in enumerate(p.blocks):
            tag = f"[p{p.number}.b{i}]"
            if b.kind == "heading":
                out.append(f"{tag} {'#' * (b.level or 1)} {b.text}")
            elif b.kind == "table" and b.rows:
                out.append(f"{tag} TABLE")
                out += ["  | " + " | ".join(r) + " |" for r in b.rows]
            else:
                out.append(f"{tag} {b.text}")
    return "\n".join(out)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for key in sys.argv[1:] or INPUTS:
        path = next(M.glob(INPUTS[key]))
        doc = parse(path.read_bytes(), path.name)
        (OUT / f"{key}.parsed.json").write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=1))
        md = anchored(doc)
        (OUT / f"{key}.anchored.md").write_text(md)
        print(key, doc.source["kind"], doc.source["parser"], len(doc.pages), "pages", sum(len(p.blocks) for p in doc.pages), "blocks", len(md), "chars", doc.warnings[:2])
