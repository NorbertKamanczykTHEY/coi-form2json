"""FieldTree (coi.extraction.tree) -> the generator's internal tree (templates' format). Mapping: generator.md pkt 1."""
import copy
import json
import re
from pathlib import Path

from ..extraction.anchors import expand, src_text
from ..extraction.tree import FieldTree, FormField, Section, ShowIf
from .build import clean_label

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
# R4: a field asking for a person's or a place's address ("Adres zameldowania", "Adres miejsca …"), not an electronic one
ADDRESS_LABEL = re.compile(r"^(inny\s+)?adres\b(?!.*(e-?mail|epuap|elektroniczn|doręcze|skrzynk|www|internet|ip\b|\blub\b))", re.I)  # "adres lub opis": free text
PLACE = re.compile(r"\bmiejsc", re.I)  # "adres miejsca …": one place for the whole request, not per row
# R3: what a dropped applicant-address section really repeats; channel, ePUAP and ADE stay
ADDRESS_PART = re.compile(r"\b(ulic\w*|kod\w*\s+poczt\w*|miejscowo\w*|numer\w*\s+(domu|budynku|lokalu|mieszkania|nieruchomo\w*)|nr\.?\s+(domu|budynku|lokalu)|dział\w*"
                          r"|kraj\w*|gmin\w*|powiat\w*|wojew\w*|poczta)\b", re.I)
OTHER_FILE = re.compile(r"^inne\b", re.I)  # R9: "Inne (podać jakie)" on the attachment list
ATTACHMENT = re.compile(r"załącz|dokument", re.I)
NAME_SPLIT = re.compile(r"^imię\s+i\s+nazwisko\b", re.I)  # R13: a person typed in by hand
COMPANY = re.compile(r"\bnazw[ay]\b|\bfirm", re.I)
STATEMENT = re.compile(r"^oświadczenie\s+(\S.*)$", re.I)  # Q34 files made by the extraction
# R1: the paper puts the condition in the text ("Wypełnić tylko w przypadku …", "W PRZYPADKU …", "jeśli … w poz. X")
COND_TEXT = re.compile(r"(?:wypełni\w*\s+(?:tylko|wyłącznie)\s+)?(?:w\s+przypadku|jeżeli|jeśli|gdy)\s+([^.;:()]{3,200})", re.I)
ONLY_IF = re.compile(r"(?i:(wypełni\w*|należy\s+wypełnić)\s+(tylko|wyłącznie)\s+w\s+przypadku)|\bW PRZYPADKU\b")
POSITION = re.compile(r"poz\w*\.?\s*([A-Z]?\d+(?:\.\d+)*)")
TEMPLATE_FILE = re.compile(r"pełnomocnictw|upoważniając|umocowani|opłat\w*\s+skarbow", re.I)


def _leaves(c):
    if not c:
        return
    if "not" in c:
        yield from _leaves(c["not"])
    elif "all" in c or "any" in c:
        for x in c.get("all") or c.get("any"):
            yield from _leaves(x)
    else:
        yield c


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
    n = {"key": f.key, "label": clean_label(f.label), "type": f.type, "required": f.optional_evidence is None and not FLAT.search(f"{f.label} {f.source_label}"),
         "meta": {"src": f.src, "source_label": f.source_label, "needs_review": f.doubt is not None, "doubt": f.doubt,
                  "description_source": f.description_source, "number": getattr(f, "number", None)}}
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
    if OTHER_FILE.match(n["label"]) and (f.type == "FILE_UPLOADER" or ATTACHMENT.search(f"{f.label} {f.source_label}")):
        n |= {"type": "FILE_UPLOADER", "required": False}  # R9: whatever else the applicant wants to attach
        n.pop("options", None)
    preset = f.preset or ("address" if f.type == "TEXT_FIELD" and ADDRESS_LABEL.match(n["label"]) else None)
    p = presets.get(preset) if preset else None
    if p and "fields" in p:  # address: the "Dane" block, keyed after the field, no prefill
        block = json.loads(json.dumps(p["fields"]).replace("{{k}}", f.key))
        for b in block:
            b["show_if"] = both(n.get("show_if"), b.get("show_if"))
            b["required"] = n["required"] and b.get("required", True)
            b["meta"] = copy.deepcopy(n["meta"])
            b["from_preset"] = True  # dictionaries come with the block, no match()
            b["block"] = (f.key, n["label"])  # R4: the paper's label titles the block's own section
        return block
    if p:
        n |= {k: v for k, v in p.items() if k == "type" or k == "validators"}
    if n["type"] == "TEXT_FIELD":
        n["validators"] = list(dict.fromkeys(n.get("validators", []) + label_validators(n, presets.get("label_validators", []))))
    return [n]


def _section_cond(n: dict, fields: list[dict]) -> bool:
    """A preset field depends on a field of its section other than its own block's country choice."""
    own = {f["key"] for f in fields if f.get("block") == n.get("block")}
    return any(lf["field"] not in own for lf in _leaves(n.get("show_if")))


def entity_duplicates(s: Section) -> set[str]:
    """Keys of a subject section that repeat the applicant entity's template data ("Dane podmiotu", "Adres siedziby"):
    the section holds the entity's seat address, so its address block, name and registry numbers are the entity's."""
    seat = lambda f: (f.preset == "address" or ADDRESS_LABEL.match(f.label)) and SEAT.search(f"{f.key} {f.label} {f.source_label}")
    if s.person_role == "third_party" or not any(seat(f) for f in s.fields):
        return set()
    return {f.key for f in s.fields if seat(f)
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
                 "show_if": n.get("show_if"), "meta": meta, "generated": True},
                n | {"show_if": both(n.get("show_if"), {"not": nie}), "label": "Numer PESEL", "generated": True},
                {"key": f"rodzaj_dokumentu_tozsamosci_{k}", "label": "Rodzaj dokumentu tożsamości", "type": "TEXT_FIELD",
                 "show_if": both(n.get("show_if"), nie), "meta": meta, "generated": True},
                {"key": f"numer_dokumentu_tozsamosci_{k}", "label": "Numer dokumentu tożsamości", "type": "TEXT_FIELD",
                 "show_if": both(n.get("show_if"), nie), "meta": meta, "generated": True}]
    return out


def split_name(fields: list[dict]) -> list[dict]:
    """R13: "Imię i nazwisko …" of a person typed in by hand -> "Imię" and "Nazwisko" (Standardy, like the template's persons);
    a label that admits a company ("… lub nazwa") stays one field."""
    out = []
    for n in fields:
        if n["type"] != "TEXT_FIELD" or not NAME_SPLIT.match(n["label"]) or COMPANY.search(n["label"]) or n.get("from_preset"):
            out.append(n)
            continue
        out += [n | {"key": f"{n['key']}_imie", "label": "Imię", "generated": True},
                n | {"key": f"{n['key']}_nazwisko", "label": "Nazwisko", "generated": True}]
    return out


def same_place(fields: list[dict], warnings: list[str], title: str) -> list[dict]:
    """R8: one blank on paper is one field: a second field with the same label, type and condition in a section goes."""
    seen, out = set(), []
    for n in fields:
        k = (n["label"].strip().lower(), n["type"], json.dumps(n.get("show_if"), sort_keys=True))
        if k in seen and not n.get("from_preset") and not n.get("generated") and n["type"] != "TEXT_BLOCK":
            warnings.append(f"sekcja {title!r}: pole {n['key']!r} powtarza etykietę {n['label']!r}, pominięto")
            continue
        seen.add(k)
        out.append(n)
    return out


def stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"\w{3,}", text.lower())} - {"lub", "oraz", "dla", "jest", "się", "tylk", "wyłąc", "przyp"}


def address_blocks(part: dict) -> list[dict]:
    """R4: an address block becomes a section titled with the paper's label ("Adres zameldowania"); a place's address
    ("adres miejsca …") leaves a repeating section, a person's address in a repeating row stays there."""
    blocks_ = [n.get("block") for n in part["fields"]]
    if not any(blocks_) or len({b for b in blocks_ if b}) == 1 and all(blocks_) and not part.get("repeating"):
        return [part]
    out, place = [], []
    for n, b in zip(part["fields"], blocks_):
        if part.get("repeating"):
            (place if b and PLACE.search(b[1]) else out).append(n)
            continue
        title = b[1] if b else part["title"]
        if not out or out[-1]["block"] != b:
            out.append({k: v for k, v in part.items() if k != "fields"} | {"title": title, "fields": [], "block": b})
        out[-1]["fields"].append(n)
    if part.get("repeating"):
        rest = [{**part, "fields": out}] if out else []
        return rest + ([{k: v for k, v in part.items() if k not in ("fields", "repeating")} | {"title": place[0]["block"][1], "repeating": False, "fields": place}] if place else [])
    return out


def conditions_from_text(pages: list[dict], blocks: dict[str, str], warnings: list[str]) -> None:
    """R1: a condition the paper writes in words ("Wypełnić tylko w przypadku …", "jeśli … w poz. 34") becomes SHOW on the
    choice field and option it names: the item number (FormField.number) narrows the field, the words pick the option.
    Without such a field, "tylko w przypadku" makes the element optional instead of required on every branch."""
    choices = [(sec, n) for pg in pages for sec in pg["sections"] for n in sec["fields"]
               if n["type"] in ("RADIO", "CHECKBOX", "SELECT") and n.get("options")]

    def number_of(c: dict) -> str:  # FormField.number, else the item number the field's source text starts with ("33. …")
        if c["meta"].get("number"):
            return c["meta"]["number"]
        first = expand(c["meta"].get("src") or [], blocks)[:1]
        m = re.match(r"\s*([A-Z]?\d+(?:\.\d+)*)[.)]\s", blocks.get(first[0], "") if first else "")
        return m[1] if m else ""

    def find(text: str, node_keys: set[str], section: dict, already: set[str]):
        text = re.sub(r"\b(poz|pkt|nr)\.", r"\1", text, flags=re.I)  # "w poz. 14": the dot does not end the condition
        hits = []
        for m in COND_TEXT.finditer(text):
            phrase = m[1]
            pos = POSITION.findall(phrase)
            scores = {}  # (field key, option) -> share of the option's word stems found in the phrase
            for sec, c in choices:
                num = number_of(c)
                if c["key"] in node_keys or (pos and not any(num == x or num.endswith("." + x) for x in pos)):
                    continue
                if sec.get("repeating") and sec is not section:
                    continue
                for o in c["options"]:
                    os_ = stems(o)
                    if os_ and (pos or len(os_) >= 2):
                        scores[(c["key"], o)] = len(os_ & stems(phrase)) / len(os_)
            if scores and (top := max(scores.items(), key=lambda kv: kv[1]))[1] >= 0.75 and top[0][0] not in already:
                # "jednorodzinnym / wielolokalowym" in one phrase: every option of that field the phrase names
                hits += [(k, o) for (k, o), sc in scores.items() if k == top[0][0] and sc >= 0.75]
        if not hits:
            return None
        same = [o for k, o in hits if k == hits[0][0]]  # "A (w przypadku X) lub B (w przypadku Y)": any of them
        return hits[0][0], list(dict.fromkeys(same))

    def leaves_of(c):
        if not c:
            return set()
        if "not" in c:
            return leaves_of(c["not"])
        if "all" in c or "any" in c:
            return set().union(*(leaves_of(x) for x in c.get("all") or c.get("any")))
        return {c["field"]}

    for pg in pages:
        for sec in pg["sections"]:
            first = set(expand(sec["fields"][0]["meta"].get("src") or [], blocks)) if sec["fields"] else set()
            own = expand(sec.get("src", []), blocks)
            heading = own[:own.index(next(a for a in own if a in first))] if first & set(own) else own[:3]
            head = " ".join([sec["title"]] + [blocks.get(a, "") for a in heading[:40]])  # the section's heading on paper
            keys = {n["key"] for n in sec["fields"]}
            hit = find(head, keys, sec, leaves_of(sec.get("show_if")))
            if hit:
                sec["show_if"] = both(sec.get("show_if"), {"field": hit[0], "in": hit[1]})
                warnings.append(f"sekcja {sec['title']!r}: warunek z treści dokumentu → SHOW na {hit[0]!r} = {hit[1]!r}")
            elif ONLY_IF.search(head) and not sec.get("show_if"):
                for n in sec["fields"]:
                    n["required"] = False
                warnings.append(f"sekcja {sec['title']!r}: dokument wypełnia ją tylko w pewnym przypadku, którego nie ma w formularzu; pola opcjonalne")
            for n in sec["fields"]:
                if n.get("from_preset") or n.get("generated"):
                    continue
                text = f"{n.get('description') or ''} {src_text(n['meta'].get('src') or [], blocks)}"
                hit = find(text, {n["key"]}, sec, leaves_of(n.get("show_if")) | leaves_of(sec.get("show_if")))
                if hit:
                    n["show_if"] = both(n.get("show_if"), {"field": hit[0], "in": hit[1]})
                    warnings.append(f"pole {n['key']!r}: warunek z treści dokumentu → SHOW na {hit[0]!r} = {hit[1]!r}")
                elif ONLY_IF.search(text) and n.get("required", True) and not n.get("show_if") and not sec.get("show_if"):
                    n["required"] = False
                    warnings.append(f"pole {n['key']!r}: dokument wypełnia je tylko w pewnym przypadku, którego nie ma w formularzu; pole opcjonalne")


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


SECTION_MAX, PAGE_MAX = 10, 12  # flow-review §5: a longer section splits, a page with more fields splits into pages


def parent(number: str | None) -> str | None:
    """The paper's group of an item: "D.1.26" -> "D.1"; a flat "26" has none."""
    return number.rsplit(".", 1)[0] if number and "." in number else None


def split_by_numbering(sec: dict, number: str | None) -> list[dict]:
    """G12: a section of more than SECTION_MAX fields splits where the paper's numbering changes group (D.1.x | D.2.x);
    without numbering on every field nothing is cut. Parts keep the title, the condition and the fields' order."""
    groups = [parent(f["meta"].get("number")) for f in sec["fields"]]
    if sec.get("repeating") or len(sec["fields"]) <= SECTION_MAX or None in groups or len(set(groups)) < 2:
        return [sec | {"number": number}]
    parts = []
    for f, g in zip(sec["fields"], groups):
        if not parts or parts[-1]["number"] != g:
            parts.append({k: v for k, v in sec.items() if k != "fields"} | {"fields": [], "number": g})
        parts[-1]["fields"].append(f)
    return parts


def split_page(title: str, secs: list[dict], taken: set[str]) -> list[dict]:
    """G12: a page of more than PAGE_MAX fields splits between sections, each new page titled after its first section;
    only when every section carries the paper's numbering (no blind cuts)."""
    if sum(len(x["fields"]) for x in secs) <= PAGE_MAX or len(secs) < 2 or any(not x.get("number") for x in secs):
        return [{"title": title, "sections": secs}]
    pages = [{"title": title, "sections": []}]
    for x in secs:
        if pages[-1]["sections"] and sum(len(y["fields"]) for y in pages[-1]["sections"]) + len(x["fields"]) > PAGE_MAX:
            t, i = x["title"], 2
            while t in taken:
                t, i = f"{x['title']} ({i})", i + 1
            taken.add(t)
            pages.append({"title": t, "sections": []})
        pages[-1]["sections"].append(x)
    return pages


def sig(sec: dict):
    """What a section asks for, without keys: identical variant blocks have the same signature."""
    return tuple((f["label"], f["type"], tuple(f.get("options") or ()), f.get("required", True)) for f in sec["fields"])


def alike(a: dict, b: dict) -> bool:
    """The same table in two versions: as many fields, at least 80% of them equal by label and type (the sum's wording may differ)."""
    x, y = sig(a), sig(b)
    return len(x) == len(y) > 1 and sum(p[:2] == q[:2] for p, q in zip(x, y)) >= 0.8 * len(x)


def merge_variant_twins(pages: list[dict], consents: list[dict]) -> tuple[dict, list[str]]:
    """G12: a block repeated for each variant (same fields, SHOW on different options of one field) becomes one section with
    SHOW on all those options. Returns the key aliases (dropped twin -> kept field) applied to every condition."""
    alias, seen, notes = {}, {}, []
    for p in pages:
        keep = []
        for sec in p["sections"]:
            c = sec.get("show_if")
            leaf = c if c and "field" in c else None
            k = (leaf["field"], sig(sec)) if leaf and sec["fields"] else None
            # R11: a twin is the same block in another variant (disjoint options), read from another place of the paper
            twins = [x for x in seen.get(k, []) if not set(leaf["in"]) & set(x["show_if"]["in"])
                     and [f["meta"]["src"] for f in x["fields"]] != [f["meta"]["src"] for f in sec["fields"]]]
            first = next((x for x in twins if x["title"] == sec["title"]), twins[0] if twins else None)
            if first is not None:
                old = first["show_if"]  # a new dict: split parts share their condition object (R11: widen only this one)
                first["show_if"] = {**old, "in": old["in"] + [v for v in leaf["in"] if v not in old["in"]]}
                for a, b in zip(sec["fields"], first["fields"]):
                    alias[a["key"]] = b["key"]
                    b["meta"]["src"] = b["meta"]["src"] + [x for x in a["meta"]["src"] if x not in b["meta"]["src"]]
                notes.append(f"sekcja {sec['title']!r}: te same pola co {first['title']!r} w innym wariancie, scalone w jedną sekcję")
                continue
            if k:
                seen.setdefault(k, []).append(sec)
            keep.append(sec)
        p["sections"] = keep
    pages[:] = [p for p in pages if p["sections"]]
    secs = [x for p in pages for x in p["sections"]]  # in paper order: a page split must not part the twins
    for i, sec in enumerate(secs):  # R1 (#8 E.1/E.2): a block next to its conditional twin, itself without SHOW, is the "otherwise" branch
        if sec.get("show_if") or not sec["fields"] or any(f.get("from_preset") for f in sec["fields"]):
            continue
        twin = next((x for x in secs[max(i - 1, 0):i + 2] if x is not sec and alike(x, sec)
                     and (c := x.get("show_if")) and "field" in c), None)
        if twin:
            sec["show_if"] = {"not": copy.deepcopy(twin["show_if"])}
            notes.append(f"sekcja {sec['title']!r}: te same pola co sąsiednia sekcja warunkowa, więc pokazana w przeciwnym przypadku")

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
        for n in [s for p in pages for s in p["sections"]]:
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
    # Section.party is the applicant's own address (residence or seat, correspondence): the template's "Dane" blocks
    # ask for it already, so the section only switches the correspondence block on
    own_address = [s for p in tree.pages for s in p.sections if getattr(s, "party", False)]
    correspondence = correspondence_asked(tree, blocks or {}) or any(
        CORRESPONDENCE.search(" ".join([s.title] + [f"{f.label} {f.source_label}" for f in s.fields])) for s in own_address)
    pages, files = [], {}
    taken = {p.title for p in tree.pages}
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
            if getattr(s, "party", False):  # R3: the template asks for the applicant's address; channel, ePUAP, ADE stay
                # only the unconditional address is the applicant's own; an address chosen in the section ("inny adres") stays
                gone = {n["key"] for n in fields if (n.get("from_preset") and not _section_cond(n, fields))
                        or (not n.get("from_preset") and n["type"] in ("TEXT_FIELD", "TEXTAREA", "SELECT")
                            and ADDRESS_PART.search(n["label"]) and not n.get("show_if"))}
                gone |= {n["key"] for n in fields if n.get("show_if") and any(lf["field"] in gone for lf in _leaves(n["show_if"]))}
                fields = [n for n in fields if n["key"] not in gone]
                warnings.append(f"sekcja {s.title!r}: adres wnioskodawcy jest w szablonie „Dane”, pominięto pola adresu"
                                + ("" if fields else " (całą sekcję)"))
            fields = same_place(split_name(fields), warnings, s.title)
            ctx = (json.dumps(cond(s.show_if), sort_keys=True), s.repeating)
            for n in [n for n in fields if n["type"] == "FILE_UPLOADER"]:  # G3/R8/R11: one uploader per document and condition
                if (m := STATEMENT.match(n["label"])) and not n.get("description"):  # R10: whose statement, what it says
                    said = re.sub(r"\s+", " ", src_text(n["meta"].get("src") or [], blocks or {})).strip()
                    n["description"] = f"Dołącz skan lub zdjęcie oświadczenia podpisanego przez: {m[1]}." + (f" Treść oświadczenia w dokumencie: „{said[:300]}”." if said else "")
                words = set(re.findall(r"\w+", n["label"].lower()))  # whole words: "Załącznik A" is not "Załącznik B"
                if TEMPLATE_FILE.search(f"{n['label']} {n['meta']['source_label']}"):
                    warnings.append(f"pole {n['key']!r}: dokument jest w szablonie (pełnomocnictwo, opłata skarbowa), pominięto")
                elif (twin := next((o for (w, c), o in files.items() if c == (ctx, json.dumps(n.get("show_if"), sort_keys=True))
                                    and words and (set(w) <= words or words <= set(w))), None)) is not None:
                    twin["required"] = twin.get("required", True) or n.get("required", True)
                    if len(n["label"]) > len(twin["label"]):
                        twin["label"] = n["label"]
                    warnings.append(f"pole {n['key']!r}: ten sam dokument co {twin['key']!r}, jeden plik")
                else:
                    files[(tuple(sorted(words)), (ctx, json.dumps(n.get("show_if"), sort_keys=True)))] = n
                    continue
                fields.remove(n)
            fields = rate_into_result(fields)
            if no_pesel:
                fields = pesel_alternative(fields)
            if not fields:
                continue
            parts = [x for part in split_multiple(s, fields) for x in split_by_numbering(part, getattr(s, "number", None))]
            parts = [y for x in parts for y in address_blocks(x)]
            for x in parts:
                x["src"] = s.src
            secs.extend(parts)
        if secs:
            pages.extend(split_page(p.title, secs, taken))
    consents = [{"text": c.text, "show_if": _all([cond(x) for x in c.show_if]), "required": getattr(c, "required", True)} for c in tree.consents]
    _, notes = merge_variant_twins(pages, consents)
    warnings += notes
    conditions_from_text(pages, blocks or {}, warnings)
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
        "proxy_id_card": bool(getattr(tree, "proxy_id_card", False)) or any(ID_CARD.search(src_text(d.src, blocks or {})) for d in tree.dropped if d.reason == "proxy_data"),
        "pages": pages,
        "consents": consents,
        "case_fee": getattr(tree, "case_fee", None),  # G8: the fee for the case itself, shown before the consents
        "case_fee_proof": bool(getattr(tree, "case_fee_proof", False)),
    }
    return internal, warnings, review


def load_presets(templates: Path) -> dict:
    return json.loads((templates / "presets.json").read_text())
