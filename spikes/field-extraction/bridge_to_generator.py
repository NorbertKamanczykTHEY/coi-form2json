"""Contract check only: normalized FieldTree -> generator spike input, per the mapping table in docs/design/generator.md §1.
The real adapter belongs to the generator; this file exists so both spikes can be run end to end today.

usage (from app/backend): PYTHONPATH=.:../spikes/field-extraction uv run python ../spikes/field-extraction/bridge_to_generator.py out/<rec>.json > in.json
"""
import json
import sys

from extract import blocks_of
from postprocess import normalize
from tree import FieldTree


def cond(si):
    c = {"field": si.field, "in": si.options}
    return {"not": c} if si.negate else c


def bridge(tree: FieldTree) -> dict:
    kinds = set(tree.applicant_kinds)
    pages = []
    for p in tree.pages:
        secs = []
        for s in p.sections:
            fields = []
            for f in s.fields:
                n = {"key": f.key, "label": f.label, "type": f.type, "required": f.optional_evidence is None}
                n |= {"options": f.options} if f.options else {}
                n |= {"show_if": cond(f.show_if)} if f.show_if else {}
                n |= {"default": f.default_value, "read_only": True} if f.default_value else {}
                n |= {"description": f.description} if f.description else {}
                fields.append(n)
            sec = {"title": s.title, "repeating": s.repeating, "fields": fields}
            sec |= {"show_if": cond(s.show_if)} if s.show_if else {}
            secs.append(sec)
        pages.append({"title": p.title, "sections": secs})
    a = tree.addressee
    return {
        "title": tree.title,
        "addressee": {"kind": "ORGAN" if a and a.kind == "organ" else "URZAD", "name": a.name if a else ""},
        "applicant": "ANY" if kinds == {"person", "legal_entity"} else "ENTITY" if kinds == {"legal_entity"} else "PERSON",
        "pages": pages,
        "consents": [{"text": c.text} for c in tree.consents],
    }


if __name__ == "__main__":
    rec = json.load(open(sys.argv[1]))
    tree, _ = normalize(FieldTree.model_validate(rec["tree"]), blocks_of(rec["form"]))
    json.dump(bridge(tree), sys.stdout, ensure_ascii=False, indent=1)
