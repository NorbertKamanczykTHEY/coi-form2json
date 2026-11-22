"""EVAL-5 rules as deterministic passes over the internal tree (adapter output): they decide from the paper's text and the
tree's shape, not from what the model happened to return. Each pass: (pages, consents, blocks, warnings) -> None, in place."""
import json
import re

from ..extraction.anchors import expand, src_text
from .build import slug

STATEMENT = re.compile(r"^oświadczenie\s+(\S.*)$", re.I)  # Q34 files: "Oświadczenie <kogo>"
SIGNED = re.compile(r"podpis|oświadcz", re.I)  # T1: the person signs or declares something on paper
ATTACHED = re.compile(r"w\s+załączeniu\s+([^.;]+)", re.I)  # T5: "… – w załączeniu kopia dla każdego psa"
EACH = re.compile(r"\bdla\s+każdego\s+(\w+)", re.I)
UPLOAD_QUESTION = re.compile(r"^czy\s+(dołącza|załącza)", re.I)  # T6 (M6): "Czy dołączasz X?" steering only X's upload
FILLER = {"kopi", "dla", "każd", "każde", "doku", "załą"}


def fields_of(pages):
    for p in pages:
        for s in p["sections"]:
            for f in s["fields"]:
                yield p, s, f


def leaves(c):
    if not c:
        return
    if "not" in c:
        yield from leaves(c["not"])
    elif "all" in c or "any" in c:
        for x in c.get("all") or c.get("any"):
            yield from leaves(x)
    else:
        yield c


def remap(c, fn):
    """Rebuild a condition with every leaf replaced by fn(leaf) (a condition, or None to drop the leaf)."""
    if not c:
        return c
    if "not" in c:
        r = remap(c["not"], fn)
        return None if r is None else {"not": r}
    if "all" in c or "any" in c:
        op = "all" if "all" in c else "any"
        parts, seen = [], set()
        for x in c[op]:
            r = remap(x, fn)
            if r is not None and (k := json.dumps(r, sort_keys=True)) not in seen:
                seen.add(k)
                parts.append(r)
        return None if not parts else parts[0] if len(parts) == 1 else {op: parts}
    return fn(c)


def every_condition(pages, consents, fn) -> None:
    for p in pages:
        for s in p["sections"]:
            s["show_if"] = remap(s.get("show_if"), fn)
            for f in s["fields"]:
                f["show_if"] = remap(f.get("show_if"), fn)
    for c in consents:
        c["show_if"] = remap(c.get("show_if"), fn)


def rename(pages, consents, alias: dict) -> None:
    if alias:
        every_condition(pages, consents, lambda c: {**c, "field": alias.get(c["field"], c["field"])})


def controls(pages, consents, key: str) -> bool:
    nodes = [s.get("show_if") for p in pages for s in p["sections"]] + [f.get("show_if") for *_, f in fields_of(pages)]
    nodes += [c.get("show_if") for c in consents]
    return any(lf["field"] == key for n in nodes for lf in leaves(n))


def split_product(pages, consents, blocks, warnings) -> None:
    """T9 (G28): a RADIO whose options are every pair of two choices ("Hodowanie charta", "Utrzymywanie mieszańca charta", …)
    becomes two RADIOs, one per axis; a condition on a pair becomes "first and second"."""
    swap = {}
    for p in pages:
        for s in p["sections"]:
            out = []
            for f in s["fields"]:
                opts = f.get("options") or []
                heads = list(dict.fromkeys(o.split(" ", 1)[0] for o in opts if " " in o))
                tails = list(dict.fromkeys(o.split(" ", 1)[1] for o in opts if " " in o))
                pairs = {(o.split(" ", 1)[0], o.split(" ", 1)[1]) for o in opts if " " in o}
                if f["type"] != "RADIO" or len(heads) < 2 or len(tails) < 2 or len(opts) != len(heads) * len(tails) \
                        or pairs != {(h, t) for h in heads for t in tails}:
                    out.append(f)
                    continue
                second = f"{f['key']}_rodzaj"
                out += [f | {"options": heads}, {**f, "key": second, "label": f"{f['label']}: doprecyzuj", "options": tails,
                                                  "description": None}]
                swap[f["key"]] = second
                warnings.append(f"pole {f['key']!r}: opcje to iloczyn dwóch wyborów, rozdzielone na dwa pola wyboru")
            s["fields"] = out

    def pair(leaf):
        if leaf["field"] not in swap:
            return leaf
        alts = [{"all": [{"field": leaf["field"], "in": [o.split(" ", 1)[0]]}, {"field": swap[leaf["field"]], "in": [o.split(" ", 1)[1]]}]}
                for o in leaf["in"] if " " in o]
        return None if not alts else alts[0] if len(alts) == 1 else {"any": alts}
    if swap:
        every_condition(pages, consents, pair)


def one_position_one_field(pages, consents, blocks, warnings) -> None:
    """T6 (M4): the same paper position read twice (same label and type, overlapping source) is one field; the copy goes and
    conditions on it point at the first. A "Czy dołączasz X?" question left steering nothing goes too (M6)."""
    seen, alias = [], {}
    for p in pages:
        for s in p["sections"]:
            keep = []
            for f in s["fields"]:
                src = set(expand(f["meta"].get("src") or [], blocks)) if f.get("meta") and not (f.get("from_preset") or f.get("generated")) else set()
                twin = next((g for g, gs in seen if src and gs & src and g["type"] == f["type"]
                             and g["label"].strip().lower() == f["label"].strip().lower()), None)
                if twin is not None:
                    alias[f["key"]] = twin["key"]
                    warnings.append(f"pole {f['key']!r}: ta sama pozycja dokumentu co {twin['key']!r}, jedno pole")
                    continue
                if src:
                    seen.append((f, src))
                keep.append(f)
            s["fields"] = keep
    rename(pages, consents, alias)
    for p in pages:
        for s in p["sections"]:
            gone = [f for f in s["fields"] if f["type"] == "RADIO" and UPLOAD_QUESTION.match(f["label"])
                    and not controls(pages, consents, f["key"])]
            for f in gone:
                warnings.append(f"pole {f['key']!r}: pytanie o załącznik, od którego nic już nie zależy, pominięto")
            s["fields"] = [f for f in s["fields"] if f not in gone]
        p["sections"] = [s for s in p["sections"] if s["fields"]]


def third_party_statements(pages, consents, blocks, warnings) -> None:
    """T1 (Q34): a file "Oświadczenie <kogo>" exists only when the paper has that person's signature or statement; it takes the
    branch condition of the person's data in its section; the applicant's consents never get that branch's condition."""
    order = list(blocks)
    branch = set()
    for p in pages:
        for s in p["sections"]:
            keep = []
            for f in s["fields"]:
                if f["type"] != "FILE_UPLOADER" or not STATEMENT.match(f["label"]) or not f.get("meta"):
                    keep.append(f)
                    continue
                anchors = [a for a in expand(f["meta"].get("src") or [], blocks) if a in blocks]
                after = order[order.index(anchors[-1]) + 1:order.index(anchors[-1]) + 4] if anchors else []
                if blocks and not SIGNED.search(" ".join(blocks[a] for a in anchors + after)):
                    warnings.append(f"pole {f['key']!r}: dokument nie ma podpisu ani oświadczenia tej osoby, plik pominięto")
                    continue
                if not f.get("show_if"):
                    conds = {json.dumps(g["show_if"], sort_keys=True) for g in s["fields"] if g is not f and g.get("show_if")
                             and not (g["type"] == "FILE_UPLOADER" and STATEMENT.match(g["label"]))}
                    people = [g for g in s["fields"] if g is not f and g["type"] not in ("FILE_UPLOADER", "TEXT_BLOCK")]
                    if len(conds) == 1 and all(g.get("show_if") for g in people if g["type"] not in ("RADIO",)):
                        f["show_if"] = json.loads(next(iter(conds)))
                        warnings.append(f"pole {f['key']!r}: plik osoby trzeciej dostał warunek jej danych")
                own = {g["key"] for g in s["fields"]}
                branch |= {lf["field"] for lf in leaves(f.get("show_if")) if lf["field"] in own}
                keep.append(f)
            s["fields"] = keep
        p["sections"] = [s for s in p["sections"] if s["fields"]]
    for c in consents:
        if any(lf["field"] in branch for lf in leaves(c.get("show_if"))):
            c["show_if"] = remap(c["show_if"], lambda lf: None if lf["field"] in branch else lf)
            warnings.append("zgoda wnioskodawcy: warunek gałęzi osoby trzeciej usunięty (jej oświadczenie idzie w pliku)")


def attachments_from_consents(pages, consents, blocks, warnings) -> None:
    """T5: "Oświadczam, że … – w załączeniu X" keeps the statement and asks for X too (in the repeating section the paper names
    with "dla każdego …"), unless an upload for X is already there."""
    subject = [s for p in pages if not p.get("template") for s in p["sections"]]
    if not subject:
        return
    uploads = [f for *_, f in fields_of(pages) if f["type"] == "FILE_UPLOADER"]
    stem = lambda t: {w[:4] for w in re.findall(r"\w{3,}", t.lower())} - FILLER
    for c in consents:
        m = ATTACHED.search(c["text"])
        if not m:
            continue
        what = m[1].strip()
        core = stem(re.sub(r"^.*?\bże\b|[–-]\s*w\s+załączeniu.*$", "", c["text"], flags=re.I))
        if any(len(stem(u["label"]) & (stem(what) | core)) >= 2 for u in uploads):
            continue
        each = EACH.search(what)
        home = next((s for s in subject if each and s.get("repeating") and each[1][:4].lower() in " ".join(
            [s["title"]] + [f["label"] for f in s["fields"]]).lower()), subject[-1])
        noun = EACH.sub("", what).strip(" –-")
        about = re.sub(r"^.*?\bże\b\s*|\s*[–-]\s*w\s+załączeniu.*$", "", c["text"], flags=re.I).strip()
        label = (noun[:1].upper() + noun[1:]) + (f": {about}" if len(noun.split()) < 3 and about else "")
        key = slug(label)
        home["fields"].append({"key": key, "label": label[:200], "type": "FILE_UPLOADER", "required": True,
                               "description": c["text"][:300], "meta": {"src": [], "source_label": what, "needs_review": False,
                                                                        "doubt": None, "description_source": "document", "number": None},
                               "generated": True})
        uploads.append(home["fields"][-1])
        warnings.append(f"oświadczenie z „w załączeniu {what}”: dodano plik {label!r}")


def controller_home(pages, consents, blocks, warnings) -> None:
    """T4: a question that steers only fields of one other section (a person's data, statements) moves into that section,
    before the first field it steers, so it is asked after the variant choice and under that section's condition."""
    for p in pages:
        for s in list(p["sections"]):
            for f in list(s["fields"]):
                if f["type"] not in ("RADIO", "CHECKBOX", "SELECT") or s.get("repeating") or f.get("from_preset") or f.get("generated"):
                    continue
                key = f["key"]
                if any(lf["field"] == key for q in pages for x in q["sections"] for lf in leaves(x.get("show_if"))) \
                        or any(lf["field"] == key for c in consents for lf in leaves(c.get("show_if"))):
                    continue
                homes = {id(x): x for q in pages for x in q["sections"] for g in x["fields"]
                         if any(lf["field"] == key for lf in leaves(g.get("show_if")))}
                if len(homes) > 1:
                    spread(p, s, f, list(homes.values()), pages, warnings)
                    continue
                if len(homes) != 1 or id(s) in homes:
                    continue
                target = next(iter(homes.values()))
                s["fields"].remove(f)
                first = next(i for i, g in enumerate(target["fields"]) if any(lf["field"] == key for lf in leaves(g.get("show_if"))))
                target["fields"].insert(first, f)
                warnings.append(f"pole {key!r}: pytanie przeniesione do sekcji {target['title']!r}, którą steruje")
        p["sections"] = [x for x in p["sections"] if x["fields"]]
    pages[:] = [p for p in pages if p["sections"]]


def spread(page, s, f, homes, pages, warnings) -> None:
    """T4 when the steered fields sit in several sections: the question follows the choice that shows those sections (the
    variant), and with every such section conditional it is shown only when one of them is."""
    conds = [h.get("show_if") for h in homes]
    if all(conds) and not f.get("show_if"):
        f["show_if"] = conds[0] if len({json.dumps(c, sort_keys=True) for c in conds}) == 1 else {"any": conds}
        warnings.append(f"pole {f['key']!r}: pytanie widoczne tylko wtedy, gdy widać sekcje, którymi steruje")
    drivers = {lf["field"] for c in conds for lf in leaves(c)}
    later = [i for i, g in enumerate(s["fields"]) if g["key"] in drivers]
    if later and s["fields"].index(f) < max(later):
        s["fields"].remove(f)
        s["fields"].insert(max(later), f)
        warnings.append(f"pole {f['key']!r}: pytanie przeniesione za wybór wariantu")


PASSES = (split_product, one_position_one_field, third_party_statements, attachments_from_consents, controller_home)


def run(pages, consents, blocks, warnings) -> None:
    for step in PASSES:
        step(pages, consents, blocks, warnings)
