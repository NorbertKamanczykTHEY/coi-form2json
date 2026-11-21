"""Spike: generator input tree -> COI JSON. Deterministic: same input, same bytes (ids included)."""
import copy
import hashlib
import html
import json
import pathlib
import re
import sys
import unicodedata
import uuid

TEMPLATES = pathlib.Path(__file__).parent / "templates"
EMPTY_HTML = "<html><head></head><body></body></html>"
INPUT_TYPES = {"TEXT_FIELD", "TEXTAREA", "NUMBER", "DATEPICKER", "RADIO", "CHECKBOX", "SELECT", "FILE_UPLOADER"}
PL = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.translate(PL)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:60] or "pole"


def stable_id(*parts) -> str:
    # deterministic, but still a valid RFC 4122 v4 string like the patterns
    return str(uuid.UUID(bytes=hashlib.sha256("/".join(parts).encode()).digest()[:16], version=4))


def keep(node, ctx) -> bool:
    return all(ctx[k] in v for k, v in (node.get("when") or {}).items())


def subst(v, ctx):
    if isinstance(v, str):
        return re.sub(r"\{\{([\w.]+)\}\}", lambda m: ctx[m[1]], v)
    return v


# ---- conditions -------------------------------------------------------------
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
    ref = idx.get(c["field"])
    if ref is None:
        raise KeyError(f"condition refers to unknown field {c['field']!r}")
    vals = [v for v in c["in"] if v in ref["options"]] if ref["options"] is not None else c["in"]
    if not vals:
        return False
    if ref.get("constant") is not None:  # single-option radio removed from the form
        return ref["constant"] in vals
    return {**c, "in": vals}


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
def desc_html(n, empty):
    if n.get("description_html"):
        return n["description_html"]
    if n.get("description"):
        return f"<html><head></head><body><p>{html.escape(n['description'])}</p></body></html>"
    return empty  # patterns: sections carry an empty HTML doc, fields an empty string


def resolve(tree: dict) -> list:
    """Assemble pages, apply `when`, placeholders and techNames. Returns pages with resolved nodes."""
    ctx = {"applicant": tree.get("applicant", "ANY"), "addressee": tree["addressee"]["kind"],
           "addressee.name": tree["addressee"]["name"], "prefill": tree.get("prefill", "MLPZ")}
    load = lambda n: json.load(open(TEMPLATES / f"{n}.json"))
    pages = [load("dane"), *copy.deepcopy(tree["pages"]), load("kontakt"), load("finish")]
    if tree.get("consents"):  # S11: document consents join the template consent field
        consent = next(f for s in pages[-2]["sections"] for f in s["fields"] if f["type"] == "CONSENT_SECTION")
        consent["consents"] += [{"html": f"<html><head></head><body><p>{html.escape(c['text'])}</p></body></html>",
                                 "required": c.get("required", True)} for c in tree["consents"]]
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
                for k in ("default", "label"):
                    f[k] = subst(f.get(k), ctx)
                if "options" in f:
                    f["options"] = [o if isinstance(o, str) else o["name"] for o in f["options"]
                                    if isinstance(o, str) or keep(o, ctx)]
    return pages


def build(tree: dict) -> dict:
    pages = resolve(tree)
    idx = {}
    for p in pages:
        for s in p["sections"]:
            for f in s["fields"]:
                opts = f.get("options") if f["type"] in ("RADIO", "CHECKBOX", "SELECT") and not f.get("dictionary") else None
                idx[f.get("key") or f["tech"]] = {"page": p["title"], "section": s["tech"], "tech": f["tech"],
                                                  "repeating": s.get("repeating", False), "options": opts}
    # a RADIO left with one option is a constant: drop it, conditions on it become True/False
    for p in pages:
        for s in p["sections"]:
            for f in s["fields"]:
                if f["type"] == "RADIO" and f.get("options") is not None and len(f["options"]) == 1:
                    idx[f.get("key") or f["tech"]]["constant"] = f["options"][0]
                    f["drop"] = True
    # simplify conditions; drop nodes that can never be shown
    for p in pages:
        for s in p["sections"]:
            s["cond"] = simplify(s.get("show_if"), idx)
            for f in s["fields"]:
                f["cond"] = simplify(f.get("show_if"), idx)
            s["fields"] = [f for f in s["fields"] if f["cond"] is not False and not f.get("drop")]
        p["sections"] = [s for s in p["sections"] if s["cond"] is not False and s["fields"]]

    title = tree["title"]
    tabs = []
    for p in pages:
        questions, y = [], 0
        for s in p["sections"]:
            children = [{"x": 0, "y": i, "rows": 1, "cols": 3, "field": field_json(f, title, idx, i)} for i, f in enumerate(s["fields"])]
            sec = node_json(s, "REPEATING_SECTION" if s.get("repeating") else "SECTION", s["title"], title, idx, y)
            sec["repeatingSectionGrid"] = children
            rows = len(children) + 1
            questions.append({"x": 0, "y": y, "rows": rows, "cols": 3, "field": sec})
            y += rows
        tabs.append({"id": stable_id(title, "tab", p["title"]), "title": p["title"], "type": p["type"], "questions": questions})
    links = [{"id": stable_id(title, "link", a["id"], b["id"]), "source": a["id"], "target": b["id"]} for a, b in zip(tabs, tabs[1:])]
    return {"title": title, "tabs": tabs, "flow": {"links": links}}


def node_json(n, typ, label, form_title, idx, order):
    states = []
    if n["cond"] is not True:
        states.append({"type": "SHOW", "query": jsonata(n["cond"], idx)})
    ro = simplify(n.get("read_only_if"), idx) if n.get("read_only_if") else False
    if ro not in (True, False):
        states.append({"type": "READ_ONLY", "query": jsonata(ro, idx)})
    return {"id": stable_id(form_title, "field", n["tech"]), "type": typ, "techName": n["tech"], "title": label or "",
            "description": desc_html(n, EMPTY_HTML if typ.endswith("SECTION") and typ != "CONSENT_SECTION" else ""),"options": [], "validation": [], "readOnly": bool(n.get("read_only")) or ro is True,
            "repeatingSectionGrid": [], "states": states, "questionOrder": order, "tooltipMessage": ""}


def field_json(f, form_title, idx, order):
    j = node_json(f, f["type"], f.get("label"), form_title, idx, order)
    if f["type"] in INPUT_TYPES:
        j["validation"] = (["REQUIRED"] if f.get("required", True) else []) + f.get("validators", [])
    if f.get("dictionary"):
        j["dictionaryName"] = f["dictionary"]  # shortcut: dictionary matching is the dictionaries thread's job
    elif f.get("options"):
        j["options"] = [{"id": o, "name": o, "techName": slug(o)} for o in f["options"]]
    for src, dst in (("multi_level", "multiLevelTree"), ("search", "searchEnabled")):
        if src in f:
            j[dst] = f[src]
    if f.get("default") is not None:
        j["defaultValue"] = f["default"]
        if isinstance(f["default"], str) and re.match(r"(MLPZ|PESEL|PESEL_ADDRESS)\.\w+$", f["default"]):
            j["defaultValueType"] = "EXTERNAL_SYSTEM"
    if f.get("consents") is not None:
        j["consentSectionConfig"] = {"consents": [{"description": c["html"], "required": c["required"]} for c in f["consents"]], "files": []}
    return j


if __name__ == "__main__":
    json.dump(build(json.load(open(sys.argv[1]))), sys.stdout, ensure_ascii=False, indent=1)
