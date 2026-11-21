"""Spike: COI JSON page -> generator input tree (inverse of gen.py).

Used once to turn the "Dane" / "Kontakt" / FINISH pages of pattern #1 into data templates,
and to turn the subject pages of #1/#5 into hand-checkable generator inputs for the regression diff.
"""
import ast
import json
import re
import sys

LEAF = re.compile(
    r"""(\$not\()?\s*\(?\s*"(?P<val>[^"]+)"\s+in\s+tabs\['(?P<page>[^']+)'\s+in\s+title\]"""
    r"""\.questions\['(?P<sec>[^']+)'\s+in\s+field\.techName\]\.field\.repeatingSectionGrid"""
    r"""\['(?P<fld>[^']+)'\s+in\s+field\.techName\]\.field\.__userAnswer\s*\)?"""
)


def query_to_cond(q: str) -> dict:
    """JSONata produced by the COI editor -> {"field","in"} / {"not"} / {"all"} / {"any"}."""
    leaves = []

    def sub(m):
        leaves.append({"field": m["fld"], "in": [m["val"]]})
        return f" {'not ' if m[1] else ''}L{len(leaves) - 1} "

    expr = LEAF.sub(sub, q)
    expr = re.sub(r"\s+", " ", expr).strip()
    node = ast.parse(expr, mode="eval").body

    def conv(n):
        if isinstance(n, ast.Name):
            return leaves[int(n.id[1:])]
        if isinstance(n, ast.UnaryOp):
            return {"not": conv(n.operand)}
        if isinstance(n, ast.BoolOp):
            return {("all" if isinstance(n.op, ast.And) else "any"): [conv(v) for v in n.values]}
        raise ValueError(f"unsupported JSONata: {q!r}")

    return conv(node)


EMPTY_HTML = "<html><head></head><body></body></html>"


def field_to_node(fl: dict) -> dict:
    n = {"key": fl["techName"], "label": fl["title"], "type": fl["type"]}
    if fl.get("description") not in (None, "", EMPTY_HTML):
        n["description_html"] = fl["description"]
    if fl.get("options"):
        n["options"] = [o["name"] for o in fl["options"]]
    for src, dst in (("dictionaryName", "dictionary"), ("defaultValue", "default"), ("multiLevelTree", "multi_level"),
                     ("searchEnabled", "search")):
        if fl.get(src) not in (None, "", False):
            n[dst] = fl[src]
    if fl.get("readOnly"):
        n["read_only"] = True
    if fl.get("consentSectionConfig"):
        n["consents"] = [{"html": c["description"], "required": c["required"]} for c in fl["consentSectionConfig"]["consents"]]
    for st in fl.get("states") or []:
        n["show_if" if st["type"] == "SHOW" else "read_only_if"] = query_to_cond(st["query"])
    return n


def tab_to_page(tab: dict) -> dict:
    sections = []
    for q in sorted(tab["questions"], key=lambda q: q["y"]):
        sec = field_to_node(q["field"])
        sec["repeating"] = sec.pop("type") == "REPEATING_SECTION"
        sec["title"] = sec.pop("label")
        sec["fields"] = [field_to_node(c["field"]) for c in sorted(q["field"].get("repeatingSectionGrid") or [], key=lambda c: c["y"])]
        sections.append(sec)
    return {"title": tab["title"], "type": tab["type"], "sections": sections}


if __name__ == "__main__":
    coi = json.load(open(sys.argv[1]))
    json.dump([tab_to_page(t) for t in coi["tabs"]], sys.stdout, ensure_ascii=False, indent=1)
