"""FieldTree (coi.extraction.tree) -> the generator's internal tree (templates' format). Mapping: generator.md pkt 1."""
import copy
import json
from pathlib import Path

from ..extraction.tree import FieldTree, FormField, ShowIf

TITLE_WORDS = ("Wniosek", "Zgłoszenie", "Deklaracja", "Oświadczenie")


def cond(si: ShowIf | None) -> dict | None:
    if si is None:
        return None
    c = {"field": si.field, "in": list(si.options)}
    return {"not": c} if si.negate else c


def both(a: dict | None, b: dict | None) -> dict | None:
    return {"all": [a, b]} if a and b else a or b


def field(f: FormField, presets: dict) -> list[dict]:
    n = {"key": f.key, "label": f.label, "type": f.type, "required": f.optional_evidence is None,
         "meta": {"src": f.src, "source_label": f.source_label, "needs_review": f.doubt is not None, "doubt": f.doubt,
                  "description_source": f.description_source}}
    if f.options:
        n["options"] = list(f.options)
    if c := cond(f.show_if):
        n["show_if"] = c
    if f.default_value is not None:  # S15: printed on paper, fixed
        n |= {"default": f.default_value, "read_only": True}
    if f.type == "TEXT_BLOCK":  # its content is the description, the patterns give it no title
        n |= {"description": f.description or f.label, "label": ""}
    elif f.description:
        n["description"] = f.description
    p = presets.get(f.preset) if f.preset else None
    if p and "fields" in p:  # address: the "Dane" block, keyed after the field, no prefill
        block = json.loads(json.dumps(p["fields"]).replace("{{k}}", f.key))
        for b in block:
            b["show_if"] = both(n.get("show_if"), b.get("show_if"))
            b["required"] = n["required"] and b.get("required", True)
            b["meta"] = copy.deepcopy(n["meta"])
            b["from_preset"] = True  # dictionaries come with the block, no match()
        return block
    if p:
        n |= {k: v for k, v in p.items() if k == "type" or k == "validators"}
    return [n]


def to_internal(tree: FieldTree, settings: dict, presets: dict) -> tuple[dict, list[str], list[dict]]:
    """-> (internal tree, warnings, needs_review)."""
    warnings = list(tree.issues)
    review = []
    if not 0 < len(tree.title) <= 255:
        review.append({"key": "title", "why": "tytuł pusty albo dłuższy niż 255 znaków"})
    elif not tree.title.startswith(TITLE_WORDS):
        review.append({"key": "title", "why": f"tytuł nie zaczyna się od {'/'.join(TITLE_WORDS)}"})
    a = tree.addressee
    if a is None:
        review.append({"key": "addressee", "why": "brak adresata, wstawiono pustą nazwę urzędu"})
    kinds = set(tree.applicant_kinds)
    applicant = "ENTITY" if kinds == {"legal_entity"} else "PERSON" if kinds == {"person"} else "ANY"
    pages = []
    for p in tree.pages:
        secs = []
        for s in p.sections:
            sec = {"title": s.title, "repeating": s.repeating, "fields": [n for f in s.fields for n in field(f, presets)]}
            if c := cond(s.show_if):
                sec["show_if"] = c
            secs.append(sec)
        pages.append({"title": p.title, "sections": secs})
    internal = {
        "title": tree.title,
        "addressee": {"kind": "ORGAN" if a and a.kind == "organ" else "URZAD", "name": a.name if a else ""},
        "applicant": applicant,
        "prefill": settings["prefill_identity"],
        "entity_option": tree.entity_option or settings["entity_option"],
        "entity_required": settings["entity_required"],
        "pages": pages,
        "consents": [{"text": c.text} for c in tree.consents],
    }
    return internal, warnings, review


def load_presets(templates: Path) -> dict:
    return json.loads((templates / "presets.json").read_text())
