"""Structural diff of two COI JSONs (ids ignored, children ordered by y, JSONata whitespace collapsed). From app/spikes/generator."""
import json
import re
import sys

PROPS = ("type", "techName", "title", "description", "readOnly", "defaultValue", "defaultValueType", "dictionaryName",
         "multiLevelTree", "searchEnabled", "questionOrder", "consentSectionConfig")


def norm_q(q):
    f = q["field"]
    n = {k: f.get(k) for k in PROPS if f.get(k) not in (None, False, "")}
    n["options"] = [(o["name"], o.get("techName")) for o in f.get("options") or []]
    n["states"] = [(s["type"], re.sub(r"\s+", "", s["query"])) for s in f.get("states") or []]
    n["validation"] = f.get("validation") or []
    n["pos"] = (q["x"], q["y"], q["rows"], q["cols"])
    n["children"] = {c["field"]["techName"]: norm_q(c) for c in sorted(f.get("repeatingSectionGrid") or [], key=lambda c: c["y"])}
    return n


def norm(coi):
    return {t["title"]: {"type": t["type"], "q": {q["field"]["techName"]: norm_q(q) for q in sorted(t["questions"], key=lambda q: q["y"])}}
            for t in coi["tabs"]}


def diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a.keys() | b.keys():
            if k not in b:
                yield f"- {path}/{k}"
            elif k not in a:
                yield f"+ {path}/{k}"
            else:
                yield from diff(a[k], b[k], f"{path}/{k}")
    elif a != b:
        yield f"~ {path}: {str(a)[:90]!r} -> {str(b)[:90]!r}"


