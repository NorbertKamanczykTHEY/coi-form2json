"""Internal tree (templates' format) -> COI JSON. Deterministic: same tree and source sha256, same bytes (ids included).
Design: app/docs/design/generator.md (pkt 2-4). Moved from app/spikes/generator/gen.py.

Internal node format: page {title, type, sections}; section {key?, title, repeating, show_if, fields, when?};
field {key?, label, type, options, show_if, required, default, read_only, description, dictionary, validators, when?, meta?}.
Conditions: {field, in: [..]} | {not} | {all: [..]} | {any: [..]}. `when` selects template variants.
"""
import copy
import hashlib
import html
import json
import re
import unicodedata
import uuid
from pathlib import Path

EMPTY_HTML = "<html><head></head><body></body></html>"
INPUT_TYPES = {"TEXT_FIELD", "TEXTAREA", "NUMBER", "DATEPICKER", "RADIO", "CHECKBOX", "SELECT", "FILE_UPLOADER"}
CHOICE = ("RADIO", "CHECKBOX", "SELECT")
PL = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
EXTERNAL = re.compile(r"(MLPZ|PESEL|PESEL_ADDRESS)\.\w+$")
SEARCH_OVER = 15  # Standardy s.5 pkt 4f: a longer list is a SELECT with a search box


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.translate(PL)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:60] or "pole"


def stable_id(*parts) -> str:
    """Q23: seeded by the file's sha256, so the same file gives the same ids; still a valid RFC 4122 v4 string."""
    return str(uuid.UUID(bytes=hashlib.sha256("/".join(parts).encode()).digest()[:16], version=4))


def keep(node, ctx) -> bool:
    return all(ctx[k] in v for k, v in (node.get("when") or {}).items())


def subst(v, ctx):
    if isinstance(v, str):
        return re.sub(r"\{\{([\w.]+)\}\}", lambda m: ctx[m[1]], v)
    if isinstance(v, list):
        return [subst(x, ctx) for x in v]
    if isinstance(v, dict):
        return {k: subst(x, ctx) for k, x in v.items()}
    return v


def html_doc(text: str) -> str:
    paras = "".join(f"<p>{html.escape(line.strip())}</p>" for line in text.splitlines() if line.strip())
    return f"<html><head></head><body>{paras}</body></html>"


# ---- conditions -------------------------------------------------------------
def leaves(c):
    if not c:
        return
    if "not" in c:
        yield from leaves(c["not"])
    elif "all" in c or "any" in c:
        for p in c.get("all") or c.get("any"):
            yield from leaves(p)
    else:
        yield c


def prune(c, bad):
    """Condition without the leaves `bad` rejects; None when nothing is left."""
    if c is None:
        return None
    if "not" in c:
        r = prune(c["not"], bad)
        return None if r is None else {"not": r}
    if "all" in c or "any" in c:
        op = "all" if "all" in c else "any"
        parts = [r for p in c[op] if (r := prune(p, bad)) is not None]
        return None if not parts else parts[0] if len(parts) == 1 else {op: parts}
    return None if bad(c) else c


def simplify(c, idx):
    """Prune leaves pointing at options that no longer exist; return True/False/condition."""
    if c is None:
        return True
    if "not" in c:
        r = simplify(c["not"], idx)
        return (not r) if isinstance(r, bool) else {"not": r}
    if "all" in c or "any" in c:
        op, absorb = ("all", False) if "all" in c else ("any", True)
        parts = [simplify(p, idx) for p in c[op]]
        if absorb in parts:
            return absorb
        parts = [p for p in parts if not isinstance(p, bool)]
        return (not absorb) if not parts else parts[0] if len(parts) == 1 else {op: parts}
    ref = idx[c["field"]]
    vals = [ref.get("rename", {}).get(v, v) for v in c["in"]]
    vals = [v for v in vals if v in ref["options"]] if ref["options"] is not None else vals
    if "constant" in ref:  # a choice field with a single option, removed from the form
        return ref["constant"] in vals
    if ref.get("required") and ref["options"] and set(ref["options"]) <= set(vals):
        return True  # G10: any option of a required choice is always chosen once the controller is filled
    return {**c, "in": vals} if vals else False


def jstr(s):
    return json.dumps(s, ensure_ascii=False)


def jsonata(c, idx, top=True) -> str:
    """Same bracketing as the COI editor: (leaf), $not(leaf-without-brackets), (A) and (B)."""
    if "not" in c:
        inner = jsonata(c["not"], idx, False)
        return f"$not({inner[1:-1] if 'field' in c['not'] and len(c['not']['in']) == 1 else inner})"
    if "all" in c or "any" in c:
        op = "all" if "all" in c else "any"
        s = f" {'and' if op == 'all' else 'or'} ".join(jsonata(p, idx, False) for p in c[op])
        return s if top else f"({s})"
    r = idx[c["field"]]
    page = r["page"].replace("'", "\\'")
    base = f"tabs['{page}' in title].questions['{r['section']}' in field.techName].field"
    if r["repeating"]:  # Reguły techniczne, example 2
        path = f"{base}.__userAnswer[$repeatingSectionIndex]['{r['tech']}' in fieldTechName].answers"
    else:
        path = f"{base}.repeatingSectionGrid['{r['tech']}' in field.techName].field.__userAnswer"
    return " or ".join(f"({jstr(v)} in {path})" for v in c["in"])


# ---- build ------------------------------------------------------------------
def resolve(tree: dict, templates: Path) -> list:
    """Assemble pages, apply `when`, placeholders and techNames. Returns pages with resolved nodes."""
    ctx = {"applicant": tree.get("applicant", "ANY"), "addressee": tree["addressee"]["kind"], "addressee.name": tree["addressee"]["name"],
           "prefill": tree.get("prefill", "MLPZ"), "pesel": tree.get("pesel", tree.get("prefill") == "PESEL"), "entity_option": tree["entity_option"],
           "entity_extract": tree.get("entity_extract", False), "proxy_id_card": tree.get("proxy_id_card", False),
           "no_pesel": tree.get("no_pesel", False), "proxy": tree.get("proxy", True), "correspondence": tree.get("correspondence", False)}
    load = lambda n: json.loads((templates / f"{n}.json").read_text())
    subject = copy.deepcopy(tree["pages"])
    for p in subject:
        p["subject"] = True
    dane = load("dane")
    at = next(i for i, s in enumerate(dane["sections"]) if s.get("key") == "__party__")
    dane["sections"][at:at + 1] = copy.deepcopy(tree.get("party", []))  # parties' sections, after the applicant's data
    pages = [dane, *subject, load("kontakt"), load("finish")]
    if tree.get("case_fee"):  # G8: the fee for the case itself, before the consents
        fee = [{"key": "informacja_o_oplacie", "label": "", "type": "TEXT_BLOCK", "description": tree["case_fee"]}]
        if tree.get("case_fee_proof"):
            fee.append({"key": "potwierdzenie_zaplaty", "label": "Potwierdzenie zapłaty", "type": "FILE_UPLOADER"})
        pages[-2]["sections"].insert(1, {"key": "oplata", "title": "Opłata", "fields": fee})
    if tree.get("consents"):  # S11: document consents join the template consent field
        section = next(s for s in pages[-2]["sections"] for f in s["fields"] if f["type"] == "CONSENT_SECTION")
        groups: dict = {}  # a consent with a condition (variant, minor/adult) gets its own CONSENT_SECTION with SHOW
        for c in tree["consents"]:
            groups.setdefault(json.dumps(c.get("show_if"), sort_keys=True), []).append(c)
        for i, (key, cs) in enumerate(groups.items()):
            items = [{"html": html_doc(c["text"]), "required": c.get("required", True)} for c in cs]
            for c in cs:
                c["field_key"] = "zgoda" if key == "null" else f"zgoda_warunkowa_{i}"  # lets needs_review name the field
            if key == "null":
                next(f for f in section["fields"] if f["type"] == "CONSENT_SECTION")["consents"] += items
            else:
                section["fields"].append({"key": f"zgoda_warunkowa_{i}", "label": "", "type": "CONSENT_SECTION",
                                          "consents": items, "show_if": cs[0]["show_if"]})
    consent_title(pages[-2])
    template_labels = {f.get("label", "").strip().lower() for p in pages if not p.get("subject") for s in p["sections"]
                       for f in s["fields"] if f.get("label") and "{{" not in f["label"]}
    for p in subject:  # G16: a subject label equal to a template one ("Nazwa organu") takes the paper's full wording
        for s in p["sections"]:
            for f in s["fields"]:
                full = re.sub(r"[\s.:…_*]+$", "", (f.get("meta") or {}).get("source_label") or "").strip()
                if f.get("label", "").strip().lower() in template_labels and full and full.lower() != f["label"].strip().lower():
                    f["label"] = full[0].upper() + full[1:]
    used = set()

    def tech(n, fallback, section=""):
        t = base = n.get("key") or slug(fallback)
        if t in used and section:  # like #1 "ulica_budynku": disambiguate by context first
            t = base = f"{base}_{section}"[:60]
        i = 2
        while t in used:
            t, i = f"{base}_{i}", i + 1
        used.add(t)
        return t

    for p in pages:
        p.setdefault("type", "MAIN")
        p["sections"] = [s for s in p["sections"] if keep(s, ctx)]
        for s in p["sections"]:
            s["tech"] = tech(s, s["title"])
            s["fields"] = [f for f in s["fields"] if keep(f, ctx)]
            for f in s["fields"]:
                f["tech"] = tech(f, f.get("label") or f["type"], s["tech"])
                for k in ("default", "label", "show_if"):
                    f[k] = subst(f.get(k), ctx)
                if f.get("read_only") and f.get("default") in (None, "", []):  # nothing to show: the applicant fills it in
                    f["read_only"] = False
                if "options" in f:
                    f["options"] = [subst(o if isinstance(o, str) else o["name"], ctx) for o in f["options"]
                                    if isinstance(o, str) or keep(o, ctx)]
            s["show_if"] = subst(s.get("show_if"), ctx)
            s["fields"] = controllers_first(s["fields"])
    return pages


def consent_title(page: dict) -> None:
    """Standardy s. 27: one statement -> "Oświadczenie", one consent -> "Zgoda", several -> "Zgody i oświadczenia"."""
    sec = next(s for s in page["sections"] if any(f["type"] == "CONSENT_SECTION" for f in s["fields"]))
    texts = [re.sub(r"<[^>]+>", "", c["html"]).strip() for f in sec["fields"] if f["type"] == "CONSENT_SECTION" for c in f["consents"]]
    if len(texts) > 1:
        sec["title"] = "Zgody i oświadczenia"
    elif texts and re.match(r"oświadczam", texts[0], re.I):
        sec["title"] = "Oświadczenie"


def controllers_first(fields: list) -> list:
    """A field that drives SHOW of others in its section moves right before the first field it controls."""
    out = list(fields)
    for f in fields:
        key = f.get("key") or f["tech"]
        deps = [i for i, g in enumerate(out) if any(lf["field"] == key for lf in leaves(g.get("show_if")))]
        if deps and min(deps) < out.index(f):
            out.remove(f)
            out.insert(min(deps), f)
    return out


def build(tree: dict, source_sha256: str, templates: Path, dictionaries=None) -> tuple[dict, list[str], dict, dict]:
    """-> (form, warnings, field_map, extra). `dictionaries(field) -> dict | None` turns a subject field into a dictionary field
    in place and returns what goes to field_map. extra: review (dropped condition parts, per field), keys (tree key ->
    {id, techName}), consents (field key per tree consent)."""
    warnings: list[str] = []
    review: list[dict] = []
    pages = resolve(tree, templates)
    field_map: dict = {}
    for p in pages:
        for s in p["sections"]:
            for f in s["fields"]:
                if p.get("subject") and dictionaries and not f.get("dictionary") and (info := dictionaries(f)):
                    f.setdefault("meta", {})["dictionary"] = info
    for p in pages:
        for s in p["sections"]:
            for f in s["fields"]:
                if f.get("meta") is None or f.get("dictionary"):
                    continue
                opts = f.get("options") or []
                if f["type"] == "CHECKBOX" and len(opts) == 1 and f.get("required", True):
                    # G9: a required one-box checkbox forces one answer; Tak/Nie lets the applicant say no
                    f |= {"type": "RADIO", "options": ["Tak", "Nie"], "rename": {opts[0]: "Tak"}, "label": f.get("label") or opts[0]}
                    warnings.append(f"pole {f['tech']!r}: wymagane pole wyboru z jedną opcją zamienione na Tak/Nie")
                elif f["type"] == "RADIO" and len(opts) > SEARCH_OVER:  # single choice only: a CHECKBOX keeps multiple choice
                    f |= {"type": "SELECT", "search": True}
    idx = {}
    for p in pages:
        for s in p["sections"]:
            for f in s["fields"]:
                opts = f.get("options") if f["type"] in CHOICE and not f.get("dictionary") else None
                idx[f.get("key") or f["tech"]] = {"page": p["title"], "section": s["tech"], "tech": f["tech"],
                                                  "repeating": s.get("repeating", False), "options": opts, "rename": f.get("rename", {}),
                                                  "required": f.get("required", True) and not f.get("read_only") and not s.get("show_if")
                                                  and not f.get("show_if")}
                if opts is not None and len(opts) == 1 and (f["type"] == "RADIO" or f.get("meta") is None):
                    # one option is no choice (Standardy s.5 pkt 4d-4e): the field goes, conditions on it hold
                    idx[f.get("key") or f["tech"]]["constant"] = opts[0]
                    f["drop"] = True

    def cond(node, section, what):
        """Simplify node's show_if. A part the COI editor cannot express (unknown field, a repeating field from outside its
        section) is cut out with a warning and a needs_review entry; the rest of the condition stays."""
        def bad(leaf):
            ref = idx.get(leaf["field"])
            if ref is None:
                why = f"warunek wyświetlania odwołuje się do pola „{leaf['field']}”, którego nie ma w formularzu"
            elif ref["repeating"] and ref["section"] != section:
                why = f"warunek wyświetlania odwołuje się do pola z sekcji powtarzalnej „{ref['section']}”, czego COI nie obsługuje"
            else:
                return False
            warnings.append(f"{what}: {why}; tę część warunku pominięto, element nie jest wymagany")
            node["cut"] = True
            review.append({"field_id": stable_id(source_sha256, "field", node["tech"]), "key": node["tech"],
                           "why": f"{why}. Tę część warunku pominięto, a element nie jest już wymagany (bez warunku byłby wymagany "
                                  "na każdej gałęzi). Sprawdź, kiedy ma być widoczny."})
            return True
        c = prune(node.get("show_if"), bad)
        r = simplify(c, idx)
        if r is False and node.get("meta") is not None:
            warnings.append(f"{what}: warunek SHOW nie pasuje do żadnej opcji pola sterującego, element usunięty")
        if r is True and c and node.get("meta") is not None:
            warnings.append(f"{what}: warunek SHOW jest zawsze spełniony (opcje pola sterującego), element zawsze widoczny")
        return r

    for p in pages:
        for s in p["sections"]:
            s["cond"] = cond(s, None, f"sekcja {s['tech']!r}")
            for f in s["fields"]:
                f["cond"] = cond(f, s["tech"], f"pole {f['tech']!r}")
                if f.get("cut") or s.get("cut"):  # G1: a cut condition must not leave the element required on every branch
                    f["required"] = False
                    for c in f.get("consents") or []:
                        c["required"] = False
            s["fields"] = [f for f in s["fields"] if f["cond"] is not False and not f.get("drop")]
        p["sections"] = [s for s in p["sections"] if s["cond"] is not False and s["fields"]]
    pages = merge_conditional_pages(pages, idx, warnings)
    later_controllers(pages, idx, warnings)

    tabs = []
    for p in pages:
        questions, y = [], 0
        for s in p["sections"]:
            children = []
            for i, f in enumerate(s["fields"]):
                j = field_json(f, source_sha256, idx, i)
                children.append({"x": 0, "y": i, "rows": 1, "cols": 3, "field": j})
                if f.get("meta") is not None:
                    field_map[j["id"]] = {"page": p["title"], "section": s["title"], "techName": f["tech"], **f["meta"]}
            sec = node_json(s, "REPEATING_SECTION" if s.get("repeating") else "SECTION", s["title"], source_sha256, idx, y)
            sec["repeatingSectionGrid"] = children
            rows = len(children) + 1  # Q21: one rule for every section
            questions.append({"x": 0, "y": y, "rows": rows, "cols": 3, "field": sec})
            y += rows
        tabs.append({"id": stable_id(source_sha256, "tab", p["title"]), "title": p["title"], "type": p["type"], "questions": questions})
    links = [{"id": stable_id(source_sha256, "link", a["id"], b["id"]), "source": a["id"], "target": b["id"]} for a, b in zip(tabs, tabs[1:])]
    keys = {k: {"id": stable_id(source_sha256, "field", v["tech"]), "techName": v["tech"]} for k, v in idx.items()}
    extra = {"review": review, "keys": keys, "consents": [c.get("field_key", "zgoda") for c in tree.get("consents", [])]}
    return {"title": tree["title"], "tabs": tabs, "flow": {"links": links}}, warnings, field_map, extra


def later_controllers(pages: list, idx: dict, warnings: list) -> None:
    """G10: SHOW must be decidable when the page is shown. A section whose condition reads a field from a later page moves
    right after that field's section; a field cannot leave its section, so it only gets a warning."""
    at = lambda title: next(i for i, p in enumerate(pages) if p["title"] == title)
    for i, p in enumerate(pages):
        for s in list(p["sections"]):
            refs = [idx[lf["field"]] for lf in leaves(s["cond"] if s["cond"] is not True else None)]
            later = [r for r in refs if at(r["page"]) > i]
            if later:
                r = max(later, key=lambda r: at(r["page"]))
                target = pages[at(r["page"])]
                p["sections"].remove(s)
                pos = next(j for j, x in enumerate(target["sections"]) if x["tech"] == r["section"]) + 1
                target["sections"].insert(pos, s)
                for f in s["fields"]:
                    idx[f.get("key") or f["tech"]]["page"] = target["title"]
                warnings.append(f"sekcja {s['tech']!r}: warunek czyta pole z późniejszej strony, sekcja przeniesiona na {target['title']!r}")
            for f in s["fields"]:
                if f["cond"] is not True and any(at(idx[lf["field"]]["page"]) > at(next(q["title"] for q in pages if s in q["sections"]))
                                                 for lf in leaves(f["cond"])):
                    warnings.append(f"pole {f['tech']!r}: warunek czyta pole z późniejszej strony")
    pages[:] = [p for p in pages if p["sections"] or not p.get("subject")]


def merge_conditional_pages(pages: list, idx: dict, warnings: list) -> list:
    """Tabs have no states in COI, so a subject page whose whole content has SHOW would show up empty. Its sections move,
    SHOW and order kept, to the nearest unconditional subject page before it (or after it); with none, all subject sections
    share one page. JSONata addresses pages by title, so the moved fields' page is updated before any query is written."""
    hidden = lambda s: s["cond"] is not True or all(f["cond"] is not True for f in s["fields"])
    subject = [p for p in pages if p.get("subject") and p["sections"]]
    keep = [p for p in subject if not all(hidden(s) for s in p["sections"])]
    if len(keep) == len(subject):
        return pages
    if not keep:  # every subject page is conditional: one shared page where the first one stood
        keep = [{"title": "Szczegóły wniosku", "type": "MAIN", "subject": True, "sections": []}]
        pages = pages[:pages.index(subject[0])] + keep + pages[pages.index(subject[0]):]
    pos = {id(p): i for i, p in enumerate(pages)}
    head = 0  # pages before the first kept one go in front of its sections, in their own order
    for p in subject:
        if any(p is k for k in keep):
            continue
        before = [k for k in keep if pos[id(k)] < pos[id(p)]]
        target = before[-1] if before else keep[0]
        if before:
            target["sections"] = target["sections"] + p["sections"]
        else:
            target["sections"] = target["sections"][:head] + p["sections"] + target["sections"][head:]
            head += len(p["sections"])
        warnings.append(f"strona {p['title']!r}: cała treść warunkowa, sekcje przeniesione na stronę {target['title']!r}")
        for sec in p["sections"]:
            for f in sec["fields"]:
                idx[f.get("key") or f["tech"]]["page"] = target["title"]
    kept = {id(k) for k in keep}
    return [p for p in pages if not p.get("subject") or id(p) in kept]


def desc_html(n, empty):
    if n.get("description_html"):
        return n["description_html"]
    if n.get("description"):
        return html_doc(n["description"])
    return empty  # patterns: sections carry an empty HTML doc, fields an empty string


def node_json(n, typ, label, sha, idx, order):
    states = []
    if n["cond"] is not True:
        states.append({"type": "SHOW", "query": jsonata(n["cond"], idx)})
    return {"id": stable_id(sha, "field", n["tech"]), "type": typ, "techName": n["tech"], "title": label or "",
            "description": desc_html(n, EMPTY_HTML if typ.endswith("SECTION") and typ != "CONSENT_SECTION" else ""), "options": [],
            "validation": [], "readOnly": bool(n.get("read_only")), "repeatingSectionGrid": [], "states": states,
            "questionOrder": order, "tooltipMessage": ""}


def field_json(f, sha, idx, order):
    j = node_json(f, f["type"], f.get("label"), sha, idx, order)
    if f["type"] in INPUT_TYPES:
        required = f.get("required", True) and not j["readOnly"]  # the applicant cannot fill a read-only field (e.g. empty office name)
        j["validation"] = (["REQUIRED"] if required else []) + f.get("validators", [])
    if f.get("dictionary"):
        j["dictionaryName"] = f["dictionary"]
    elif f.get("options"):
        j["options"] = [{"id": o, "name": o, "techName": slug(o)} for o in f["options"]]
    for src, dst in (("multi_level", "multiLevelTree"), ("search", "searchEnabled")):
        if src in f:
            j[dst] = f[src]
    if f.get("default") is not None:
        j["defaultValue"] = f["default"]
        if isinstance(f["default"], str) and EXTERNAL.match(f["default"]):
            j["defaultValueType"] = "EXTERNAL_SYSTEM"
    if f.get("consents") is not None:
        j["consentSectionConfig"] = {"consents": [{"description": c["html"], "required": c["required"]} for c in f["consents"]], "files": []}
    return j
