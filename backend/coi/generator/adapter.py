"""FieldTree (coi.extraction.tree) -> the generator's internal tree (templates' format). Mapping: generator.md pkt 1."""
import copy
import json
import re
from pathlib import Path

from ..extraction.anchors import src_text
from ..extraction.tree import FieldTree, FormField, Section, ShowIf

TITLE_WORDS = ("Wniosek", "Zgłoszenie", "Deklaracja", "Oświadczenie")
PESEL = re.compile(r"\bPESEL\b", re.I)
SEAT = re.compile(r"siedzib", re.I)  # "adres siedziby": the applicant entity's own address
ENTITY_ID = re.compile(r"^nazwa\b|\b(nip|regon|krs)\b", re.I)  # name and registry numbers the "Dane podmiotu" template asks for


def cond(si: ShowIf | None) -> dict | None:
    if si is None:
        return None
    c = {"field": si.field, "in": list(si.options)}
    return {"not": c} if si.negate else c


def both(a: dict | None, b: dict | None) -> dict | None:
    return {"all": [a, b]} if a and b else a or b


def _all(conds: list) -> dict | None:
    out = None
    for c in conds:
        out = both(out, c)
    return out


def label_validators(n: dict, rules: list) -> list[str]:
    """Reguły techniczne validators chosen from the wording of a text field's label (PESEL, NIP, ePUAP, ADE, ...)."""
    text = f"{n['label']} {n['meta']['source_label']}".lower()
    return [v for rx, v in rules if re.search(rx, text)]


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
    if n["type"] == "TEXT_FIELD":
        n["validators"] = list(dict.fromkeys(n.get("validators", []) + label_validators(n, presets.get("label_validators", []))))
    return [n]


def entity_duplicates(s: Section) -> set[str]:
    """Keys of a subject section that repeat the applicant entity's template data ("Dane podmiotu", "Adres siedziby"):
    the section holds the entity's seat address, so its address block, name and registry numbers are the entity's."""
    if s.person_role == "third_party" or not any(f.preset == "address" and SEAT.search(f"{f.key} {f.label} {f.source_label}") for f in s.fields):
        return set()
    return {f.key for f in s.fields if (f.preset == "address" and SEAT.search(f"{f.key} {f.label} {f.source_label}"))
            or (f.type == "TEXT_FIELD" and ENTITY_ID.search(f.label))}


def to_internal(tree: FieldTree, settings: dict, presets: dict, blocks: dict[str, str] | None = None) -> tuple[dict, list[str], list[dict]]:
    """-> (internal tree, warnings, needs_review). `blocks` (anchor -> text) lets the paper's own wording decide template fields."""
    warnings = list(tree.issues)
    review = []
    if not 0 < len(tree.title) <= 255:
        review.append({"key": "title", "why": "tytuł pusty albo dłuższy niż 255 znaków"})
    elif not tree.title.startswith(TITLE_WORDS):
        review.append({"key": "title", "why": f"tytuł nie zaczyna się od {'/'.join(TITLE_WORDS)}"})
    a = tree.addressee
    if a is None or not a.name.strip():
        review.append({"key": "addressee", "why": "brak adresata, pole nazwy urzędu do uzupełnienia"})
    kinds = set(tree.applicant_kinds)
    applicant = "ENTITY" if kinds == {"legal_entity"} else "PERSON" if kinds == {"person"} else "ANY"
    pages = []
    for p in tree.pages:
        secs = []
        for s in p.sections:
            dup = entity_duplicates(s) if applicant == "ENTITY" else set()
            if dup:
                warnings.append(f"sekcja {s.title!r}: pominięto {', '.join(sorted(dup))}, bo powtarzają dane podmiotu ze strony „Dane”")
            fields = [n for f in s.fields if f.key not in dup for n in field(f, presets)]
            if not fields:
                continue
            sec = {"title": s.title, "repeating": s.repeating, "fields": fields}
            if c := cond(s.show_if):
                sec["show_if"] = c
            secs.append(sec)
        if secs:
            pages.append({"title": p.title, "sections": secs})
    internal = {
        "title": tree.title,
        "addressee": {"kind": "ORGAN" if a and a.kind == "organ" else "URZAD", "name": a.name if a else ""},
        "applicant": applicant,
        "prefill": settings["prefill_identity"],
        # the applicant's PESEL field: by setting, or because the paper asks for it among the applicant's data (moved to "Dane")
        "pesel": settings["prefill_identity"] == "PESEL" or any(
            PESEL.search(src_text(d.src, blocks or {})) for d in tree.dropped if d.reason == "applicant_data"),
        "entity_option": tree.entity_option or settings["entity_option"],
        "entity_required": settings["entity_required"],
        "pages": pages,
        "consents": [{"text": c.text, "show_if": _all([cond(x) for x in c.show_if])} for c in tree.consents],
    }
    return internal, warnings, review


def load_presets(templates: Path) -> dict:
    return json.loads((templates / "presets.json").read_text())
