"""FieldTree (coi.extraction.tree) -> the generator's internal tree (templates' format). Mapping: generator.md pkt 1."""
import copy
import json
import re
from pathlib import Path

from ..extraction.anchors import expand, src_text
from ..extraction.tree import FieldTree, FormField, Section, ShowIf

TITLE_WORDS = ("Wniosek", "Zgłoszenie", "Deklaracja", "Oświadczenie")
PESEL = re.compile(r"\bPESEL\b", re.I)
SEAT = re.compile(r"siedzib", re.I)  # "adres siedziby": the applicant entity's own address
ID_CARD = re.compile(r"dowod\w* osobist", re.I)  # the paper asks the proxy for an ID card number
# the paper lets an applicant without PESEL give an identity document instead (#8: "nie posiadające numeru PESEL wpisują
# numer dokumentu tożsamości"); read on the whole text, the sentence usually sits in the instructions and spans blocks
NO_PESEL = re.compile(r"(nie\s*posiada\w*|brak\w*|bez)\s+(numeru\s+)?PESEL\b.{0,150}?dokument\w*\s+tożsamości", re.I | re.S)
CORRESPONDENCE = re.compile(r"adres\w*\s+(do\s+)?korespondenc", re.I)  # the paper has a separate address for letters
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
NOT_APPLICANT = {"rodo", "legal_info", "office_use"}  # blocks where "PESEL" is prose, not a field of the applicant
ENTITY_ID = re.compile(r"^nazwa\b|\b(nip|regon|krs)\b", re.I)  # name and registry numbers the "Dane podmiotu" template asks for
FLAT = re.compile(r"\b(numer|nr)\.?\s+(lokalu|mieszkania)\b", re.I)  # Standardy: a flat number is never required ("Brak numeru lokalu")
DATE_MASK = re.compile(r"^\W*(DD|RRRR|YYYY|MM)([-./ ]*(DD|MM|RRRR|YYYY|RR))+\W*$", re.I)  # a date mask from the paper: the picker shows the format
X_MASK = re.compile(r"X{8,}|_{8,}")  # "w formacie XXXX…": a mask, not a hint
ACCOUNT = re.compile(r"rachun|konto|konta", re.I)
# the template's proxy section asks for these (S12); a subject uploader for them is a duplicate
TEMPLATE_FILE = re.compile(r"pełnomocnictw|upoważniając|umocowani|opłat\w*\s+skarbow", re.I)


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
    n = {"key": f.key, "label": f.label, "type": f.type, "required": f.optional_evidence is None and not FLAT.search(f"{f.label} {f.source_label}"),
         "meta": {"src": f.src, "source_label": f.source_label, "needs_review": f.doubt is not None, "doubt": f.doubt,
                  "description_source": f.description_source}}
    if f.options:
        n["options"] = list(f.options)
    if c := cond(f.show_if):
        n["show_if"] = c
    if f.type == "TEXT_BLOCK":  # its content is the description, the patterns give it no title; a block shows no defaultValue (G6)
        text = f.description or f.label
        if f.default_value and f.default_value not in text:
            text = f"{text}: {f.default_value}"
        n |= {"description": text, "label": ""}
    elif f.default_value is not None and not (f.type == "DATEPICKER" and not ISO_DATE.match(f.default_value)):
        n |= {"default": f.default_value, "read_only": True}  # S15: printed on paper, fixed; a date only as YYYY-MM-DD
    desc = f.description if f.type != "TEXT_BLOCK" else None
    if desc and f.type == "DATEPICKER" and DATE_MASK.match(desc):
        desc = None
    elif desc and X_MASK.search(desc):
        desc = "Wpisz 26 cyfr numeru rachunku." if ACCOUNT.search(f"{f.label} {f.source_label}") else None
    if desc:
        n["description"] = desc
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


def split_multiple(s: Section, fields: list[dict]) -> list[dict]:
    """COI has no multi-file uploader and no section inside a section (R2): a `multiple` upload becomes a REPEATING_SECTION
    with one optional FILE_UPLOADER placed right under the last required upload of its section; the fields after it continue
    in a section with the same title."""
    many = [n for n in fields if n["key"] in {f.key for f in s.fields if f.multiple}]
    rest = [n for n in fields if n not in many]
    show = cond(s.show_if)
    part = lambda fs: {"title": s.title, "repeating": s.repeating, "fields": fs} | ({"show_if": show} if show else {})
    if not many:
        return [part(rest)] if rest else []
    cut = max((i + 1 for i, n in enumerate(rest) if n["type"] == "FILE_UPLOADER" and n.get("required", True)), default=len(rest))
    out = [part(rest[:cut])] if rest[:cut] else []
    out += [{"title": n["label"], "repeating": True, "show_if": both(show, n.pop("show_if", None)), "fields": [n | {"required": False}]}
            for n in many]
    return out + ([part(rest[cut:])] if rest[cut:] else [])


def applicant_pesel(tree: FieldTree, blocks: dict[str, str]) -> bool:
    """The paper asks for a PESEL that is not a subject field (third party) nor prose (RODO, instructions): the applicant's own.
    Read from the source text itself, so it does not depend on how the model labelled the dropped block."""
    elsewhere = {a for p in tree.pages for s in p.sections for f in s.fields
                 if f.preset == "pesel" or PESEL.search(f"{f.label} {f.source_label}") for a in expand(f.src, blocks)}
    elsewhere |= {a for d in tree.dropped if d.reason in NOT_APPLICANT for a in expand(d.src, blocks)}
    return any(PESEL.search(t) for a, t in blocks.items() if a not in elsewhere)


def correspondence_asked(tree: FieldTree, blocks: dict[str, str]) -> bool:
    """A correspondence address of the applicant: in the text, outside third-party sections and outside prose (RODO, instructions)."""
    elsewhere = {a for p in tree.pages for s in p.sections if s.person_role == "third_party"
                 for f in s.fields for a in expand(f.src + s.src, blocks)}
    elsewhere |= {a for d in tree.dropped if d.reason in NOT_APPLICANT for a in expand(d.src, blocks)}
    return any(CORRESPONDENCE.search(t) for a, t in blocks.items() if a not in elsewhere)


def correspondence_duplicates(s: Section) -> set[str]:
    """Keys the template's correspondence block replaces: the address itself, its "is it different" toggle, fields shown by it."""
    if s.person_role == "third_party":
        return set()
    own = lambda f: CORRESPONDENCE.search(f"{f.key.replace('_', ' ')} {f.label} {f.source_label}") or "korespondencyjn" in f.key
    dup = {f.key for f in s.fields if (f.preset == "address" or f.type in ("RADIO", "CHECKBOX")) and own(f)}
    return dup | {f.key for f in s.fields if f.show_if and f.show_if.field in dup}


def pesel_alternative(fields: list[dict]) -> list[dict]:
    """A person typed in by hand (spouse, other person) gets the same no-PESEL alternative as the applicant."""
    out = []
    for n in fields:
        if n["type"] != "TEXT_FIELD" or "PESEL" not in n.get("validators", []):
            out.append(n)
            continue
        k, nie = n["key"], {"field": f"czy_ma_numer_pesel_{n['key']}", "in": ["Nie"]}
        meta = n["meta"]
        out += [{"key": nie["field"], "label": "Czy ta osoba ma numer PESEL?", "type": "RADIO", "options": ["Tak", "Nie"],
                 "show_if": n.get("show_if"), "meta": meta},
                n | {"show_if": both(n.get("show_if"), {"not": nie})},
                {"key": f"rodzaj_dokumentu_tozsamosci_{k}", "label": "Rodzaj dokumentu tożsamości", "type": "TEXT_FIELD",
                 "show_if": both(n.get("show_if"), nie), "meta": meta},
                {"key": f"numer_dokumentu_tozsamosci_{k}", "label": "Numer dokumentu tożsamości", "type": "TEXT_FIELD",
                 "show_if": both(n.get("show_if"), nie), "meta": meta}]
    return out


def rate_into_result(fields: list[dict]) -> list[dict]:
    """G6 (ADR 0019): a short rate block ("Stawka 38 zł") goes into the description of the nearest NUMBER of its section
    shown under the same condition (the following one on a tie); with none, it stays a text block."""
    moved = set()
    for i, n in enumerate(fields):
        if n["type"] != "TEXT_BLOCK" or len(n["description"]) > 120:
            continue
        near = sorted((abs(j - i) - (j > i) * 0.5, j) for j, m in enumerate(fields)
                      if m["type"] == "NUMBER" and m.get("show_if") == n.get("show_if"))
        if near:
            m = fields[near[0][1]]
            m["description"] = f"{m['description']} {n['description']}" if m.get("description") else n["description"]
            moved.add(i)
    return [n for i, n in enumerate(fields) if i not in moved]


def sig(sec: dict):
    """What a section asks for, without keys: identical variant blocks have the same signature."""
    return tuple((f["label"], f["type"], tuple(f.get("options") or ()), f.get("required", True)) for f in sec["fields"])


def merge_variant_twins(pages: list[dict], consents: list[dict], party: list[dict]) -> tuple[dict, list[str]]:
    """G12: a block repeated for each variant (same fields, SHOW on different options of one field) becomes one section with
    SHOW on all those options. Returns the key aliases (dropped twin -> kept field) applied to every condition."""
    alias, seen, notes = {}, {}, []
    for p in pages:
        keep = []
        for sec in p["sections"]:
            c = sec.get("show_if")
            leaf = c if c and "field" in c else None
            k = (leaf["field"], sig(sec)) if leaf and sec["fields"] else None
            if k in seen:
                first = seen[k]
                first["show_if"]["in"] += [v for v in leaf["in"] if v not in first["show_if"]["in"]]
                for a, b in zip(sec["fields"], first["fields"]):
                    alias[a["key"]] = b["key"]
                    b["meta"]["src"] = b["meta"]["src"] + [x for x in a["meta"]["src"] if x not in b["meta"]["src"]]
                notes.append(f"sekcja {sec['title']!r}: te same pola co {first['title']!r} w innym wariancie, scalone w jedną sekcję")
                continue
            if k:
                seen[k] = sec
            keep.append(sec)
        p["sections"] = keep
    pages[:] = [p for p in pages if p["sections"]]

    def ren(c):
        if not c:
            return c
        if "not" in c:
            return {"not": ren(c["not"])}
        if "all" in c or "any" in c:
            op = "all" if "all" in c else "any"
            return {op: [ren(x) for x in c[op]]}
        return {**c, "field": alias.get(c["field"], c["field"])}
    if alias:
        for n in [s for p in pages for s in p["sections"]] + party:
            n["show_if"] = ren(n.get("show_if"))
            for f in n["fields"]:
                f["show_if"] = ren(f.get("show_if"))
        for c in consents:
            c["show_if"] = ren(c.get("show_if"))
    return alias, notes


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
    no_pesel = bool(NO_PESEL.search(" ".join((blocks or {}).values())))
    correspondence = correspondence_asked(tree, blocks or {})
    pages, party, files = [], [], {}
    for p in tree.pages:
        secs = []
        for s in p.sections:
            dup = entity_duplicates(s) if applicant == "ENTITY" else set()
            if dup:
                warnings.append(f"sekcja {s.title!r}: pominięto {', '.join(sorted(dup))}, bo powtarzają dane podmiotu ze strony „Dane”")
            if correspondence and (kor := correspondence_duplicates(s)):
                warnings.append(f"sekcja {s.title!r}: pominięto {', '.join(sorted(kor))}, adres do korespondencji jest w szablonie „Dane”")
                dup |= kor
            fields = [n for f in s.fields if f.key not in dup for n in field(f, presets)]
            for n in [n for n in fields if n["type"] == "FILE_UPLOADER"]:  # G3: one uploader per document, none for template ones
                name = re.sub(r"\W+", " ", n["label"]).strip().lower()
                if TEMPLATE_FILE.search(f"{n['label']} {n['meta']['source_label']}"):
                    warnings.append(f"pole {n['key']!r}: dokument jest w szablonie (pełnomocnictwo, opłata skarbowa), pominięto")
                elif name in files:
                    files[name]["required"] = files[name].get("required", True) or n.get("required", True)
                    warnings.append(f"pole {n['key']!r}: ten sam dokument co {files[name]['key']!r}, jeden plik")
                else:
                    files[name] = n
                    continue
                fields.remove(n)
            fields = rate_into_result(fields)
            if no_pesel:
                fields = pesel_alternative(fields)
            if not fields:
                continue
            # Standardy s.6: the first page holds the data of every party of the proceedings, not only the applicant's
            (party if getattr(s, "party", False) else secs).extend(split_multiple(s, fields))
        if secs:
            pages.append({"title": p.title, "sections": secs})
    consents = [{"text": c.text, "show_if": _all([cond(x) for x in c.show_if]), "required": getattr(c, "required", True)} for c in tree.consents]
    _, notes = merge_variant_twins(pages, consents, party)
    warnings += notes
    entity_option = settings["entity_option"]  # G5: the Standardy's text; the paper's wording names a role, not the option
    if tree.entity_option and tree.entity_option != entity_option:
        warnings.append(f"opcja podmiotu z dokumentu {tree.entity_option!r} zastąpiona opcją ze Standardów {entity_option!r}")
    internal = {
        "title": tree.title,
        "addressee": {"kind": "ORGAN" if a and a.kind == "organ" else "URZAD", "name": a.name if a else ""},
        "applicant": applicant,
        "prefill": settings["prefill_identity"],
        # the applicant's PESEL field: by setting, or because the paper asks for it
        "pesel": settings["prefill_identity"] == "PESEL" or applicant_pesel(tree, blocks or {}),
        "entity_option": entity_option,
        "entity_extract": bool(getattr(tree, "entity_extract_required", False)),  # registry extract from every entity applicant
        "no_pesel": no_pesel,
        "correspondence": correspondence,
        "party": party,
        "proxy_id_card": bool(getattr(tree, "proxy_id_card", False)) or any(ID_CARD.search(src_text(d.src, blocks or {})) for d in tree.dropped if d.reason == "proxy_data"),
        "pages": pages,
        "consents": consents,
        "case_fee": getattr(tree, "case_fee", None),  # G8: the fee for the case itself, shown before the consents
        "case_fee_proof": bool(getattr(tree, "case_fee_proof", False)),
    }
    return internal, warnings, review


def load_presets(templates: Path) -> dict:
    return json.loads((templates / "presets.json").read_text())
