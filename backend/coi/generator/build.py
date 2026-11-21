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
    vals = [v for v in c["in"] if v in ref["options"]] if ref["options"] is not None else c["in"]
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
           "prefill": tree.get("prefill", "MLPZ"), "pesel": tree.get("pesel", tree.get("prefill") == "PESEL"), "entity_option": tree["entity_option"], "entity_required": tree.get("entity_required", True)}
    load = lambda n: json.loads((templates / f"{n}.json").read_text())
    subject = copy.deepcopy(tree["pages"])
    for p in subject:
        p["subject"] = True
    pages = [load("dane"), *subject, load("kontakt"), load("finish")]
    if tree.get("consents"):  # S11: document consents join the template consent field
        section = next(s for s in pages[-2]["sections"] for f in s["fields"] if f["type"] == "CONSENT_SECTION")
        groups: dict = {}  # a consent with a condition (variant, minor/adult) gets its own CONSENT_SECTION with SHOW
        for c in tree["consents"]:
            groups.setdefault(json.dumps(c.get("show_if"), sort_keys=True), []).append(c)
        for i, (key, cs) in enumerate(groups.items()):
            items = [{"html": html_doc(c["text"]), "required": c.get("required", True)} for c in cs]
            if key == "null":
                next(f for f in section["fields"] if f["type"] == "CONSENT_SECTION")["consents"] += items
            else:
                section["fields"].append({"key": f"zgoda_warunkowa_{i}", "label": "", "type": "CONSENT_SECTION",
                                          "consents": items, "show_if": cs[0]["show_if"]})
    consent_title(pages[-2])
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
                if isinstance(f.get("required"), str):  # a setting name, e.g. "entity_required" (Q31)
                    f["required"] = ctx[f["required"]]
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


def build(tree: dict, source_sha256: str, templates: Path, dictionaries=None) -> tuple[dict, list[str], dict]:
    """-> (form, warnings, field_map). `dictionaries(field) -> dict | None` turns a subject field into a dictionary field
    in place and returns what goes to field_map."""
    warnings: list[str] = []
    pages = resolve(tree, templates)
    field_map: dict = {}
    for p in pages:
        for s in p["sections"]:
            for f in s["fields"]:
                if p.get("subject") and dictionaries and not f.get("dictionary") and (info := dictionaries(f)):
                    f.setdefault("meta", {})["dictionary"] = info
    idx = {}
    for p in pages:
        for s in p["sections"]:
            for f in s["fields"]:
                opts = f.get("options") if f["type"] in CHOICE and not f.get("dictionary") else None
                idx[f.get("key") or f["tech"]] = {"page": p["title"], "section": s["tech"], "tech": f["tech"],
                                                  "repeating": s.get("repeating", False), "options": opts}

    def cond(node, section, what):
        """Simplify node's show_if; a condition the COI editor cannot express is dropped with a warning (node stays visible)."""
        c = node.get("show_if")
        for leaf in leaves(c):
            ref = idx.get(leaf["field"])
            if ref is None:
                warnings.append(f"{what}: warunek SHOW wskazuje nieistniejące pole {leaf['field']!r}, pominięty")
                return True
            if ref["repeating"] and ref["section"] != section:
                warnings.append(f"{what}: warunek SHOW na polu z sekcji powtarzalnej {ref['section']!r}, JSONata COI tego nie wyrazi, pominięty")
                return True
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
            s["fields"] = [f for f in s["fields"] if f["cond"] is not False]
        p["sections"] = [s for s in p["sections"] if s["cond"] is not False and s["fields"]]
        if p.get("subject") and p["sections"] and all(s["cond"] is not True for s in p["sections"]):
            warnings.append(f"strona {p['title']!r}: wszystkie sekcje mają SHOW, strona może wyświetlić się pusta")

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
    return {"title": tree["title"], "tabs": tabs, "flow": {"links": links}}, warnings, field_map


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
