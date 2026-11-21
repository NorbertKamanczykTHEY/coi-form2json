"""Spike: final validator = JSON Schema + rules 1-6 (Reguły techniczne) + reference checks on JSONata."""
import json
import pathlib
import re
import sys

import jsonschema

SCHEMA = json.load(open(pathlib.Path(__file__).resolve().parents[2] / "backend/coi/form_schema.json"))
INPUT = {"TEXT_FIELD", "TEXTAREA", "NUMBER", "DATEPICKER", "RADIO", "CHECKBOX", "SELECT", "FILE_UPLOADER"}
SECTIONS = {"SECTION", "REPEATING_SECTION"}
REF = re.compile(r"""(?:"([^"]+)" in )?tabs\['([^']+)' in title\]\.questions\['([^']+)' in field\.techName\]\.field"""
                 r"""(?:\.repeatingSectionGrid\['([^']+)' in field\.techName\]|\.__userAnswer\[\$repeatingSectionIndex\]\['([^']+)' in fieldTechName\])""")


def validate(form: dict) -> list[str]:
    errs = []
    # schema: SELECT defaultValue is an array in the patterns but a string in the schema -> known, skipped
    for e in jsonschema.Draft202012Validator(SCHEMA).iter_errors(form):
        if not (e.validator == "type" and list(e.path)[-1:] == ["defaultValue"] and isinstance(e.instance, list)):
            errs.append(f"schema: {'/'.join(map(str, e.path))}: {e.message}")
    tabs = form.get("tabs", [])
    if not 0 < len(form.get("title", "")) <= 255:
        errs.append("title: empty or longer than 255")
    if len(tabs) < 2:
        errs.append("R1: fewer than 2 tabs")
    if tabs and (tabs[-1]["type"] != "FINISH" or any(t["type"] != "MAIN" for t in tabs[:-1])):
        errs.append("R1: last tab must be FINISH, the rest MAIN")
    index, techs = {}, {}
    for t in tabs:
        if not t["questions"]:
            errs.append(f"R2: tab '{t['title']}' has no fields")
        for q in t["questions"]:
            s = q["field"]
            if s["type"] not in SECTIONS:
                errs.append(f"R2: '{s['techName']}' on tab '{t['title']}' is not inside a section")
                continue
            for c in s.get("repeatingSectionGrid") or []:
                f = c["field"]
                techs.setdefault(f["techName"], []).append(t["title"])
                index[(t["title"], s["techName"], f["techName"])] = f
                if f["type"] in SECTIONS:
                    errs.append(f"R2: nested section '{f['techName']}'")
                if t["type"] == "FINISH" and f["type"] in INPUT | {"CONSENT_SECTION"}:
                    errs.append(f"R3: input field '{f['techName']}' on FINISH tab")
                if f["type"] in INPUT and not isinstance(f.get("validation"), list):
                    errs.append(f"R4: '{f['techName']}' validation is not a list")
                if f["type"] in ("SELECT", "RADIO", "CHECKBOX") and not (f.get("options") or f.get("dictionaryName")):
                    errs.append(f"choice field '{f['techName']}' has neither options nor dictionaryName")
                if f.get("dictionaryName") and f.get("options"):
                    errs.append(f"'{f['techName']}' has dictionaryName and options")
    errs += [f"techName '{k}' used {len(v)}x" for k, v in techs.items() if len(v) > 1]
    ids = [t["id"] for t in tabs]
    chain = [(l["source"], l["target"]) for l in form.get("flow", {}).get("links", [])]
    if any(a not in ids or b not in ids for a, b in chain) or {i for l in chain for i in l} != set(ids):
        errs.append("R5: flow links do not connect all tabs")
    for t in tabs:  # R6: every JSONata reference must resolve, and compared values must be real options
        for q in t["questions"]:
            for node in [q["field"], *[c["field"] for c in q["field"].get("repeatingSectionGrid") or []]]:
                for st in node.get("states") or []:
                    for val, page, sec, f1, f2 in REF.findall(st["query"]):
                        target = index.get((page, sec, f1 or f2))
                        if target is None:
                            errs.append(f"R6: '{node['techName']}' refers to missing {page}/{sec}/{f1 or f2}")
                        elif val and target.get("options") and val not in [o["name"] for o in target["options"]]:
                            errs.append(f"R6: '{node['techName']}' compares with '{val}', not an option of {f1 or f2}")
    return errs


if __name__ == "__main__":
    for p in sys.argv[1:]:
        e = validate(json.load(open(p)))
        print(p, "OK" if not e else f"{len(e)} problems")
        print("\n".join("  " + x for x in e[:30]))
