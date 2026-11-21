"""Final validator (generator.md pkt 6): JSON Schema + rules 1-6 of "Reguły techniczne" + JSONata references.
Serves the generator, POST /api/v1/forms/validate and PUT /forms/{id}. Errors: [{path, message, rule}]."""
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA = Draft202012Validator(json.loads((Path(__file__).resolve().parent.parent / "form_schema.json").read_text()))
INPUT = {"TEXT_FIELD", "TEXTAREA", "NUMBER", "DATEPICKER", "RADIO", "CHECKBOX", "SELECT", "FILE_UPLOADER"}
SECTIONS = {"SECTION", "REPEATING_SECTION"}
REF = re.compile(r"""(?:"((?:[^"\\]|\\.)*)" in )?tabs\['((?:[^'\\]|\\.)*)' in title\]\.questions\['([^']+)' in field\.techName\]\.field"""
                 r"""(?:\.repeatingSectionGrid\['([^']+)' in field\.techName\]|\.__userAnswer\[\$repeatingSectionIndex\]\['([^']+)' in fieldTechName\])""")


def validate(form) -> list[dict]:
    errs = []

    def err(rule, path, message):
        errs.append({"path": path, "message": message, "rule": rule})

    for e in SCHEMA.iter_errors(form):
        # known conflict: the patterns' SELECT defaultValue is an array, the schema says string
        if not (e.validator == "type" and list(e.path)[-1:] == ["defaultValue"] and isinstance(e.instance, list)):
            err("schema", "/" + "/".join(map(str, e.absolute_path)), e.message)
    if errs:
        return errs  # the rules below assume the schema's shape
    try:
        _rules(form, err)
    except (KeyError, TypeError, AttributeError, IndexError) as e:  # shapes the schema does not forbid
        err("structure", "", f"unexpected structure: {type(e).__name__} {e}")
    return errs


def _rules(form: dict, err) -> None:
    tabs = form.get("tabs") or []
    if not 0 < len(form.get("title") or "") <= 255:
        err("title", "/title", "title is empty or longer than 255 characters")
    if len(tabs) < 2:
        err("R1", "/tabs", "a form needs at least 2 tabs")
    if tabs and (tabs[-1].get("type") != "FINISH" or any(t.get("type") != "MAIN" for t in tabs[:-1])):
        err("R1", "/tabs", "the last tab must be FINISH, the others MAIN")
    index, techs = {}, {}
    for ti, t in enumerate(tabs):
        tp = f"/tabs/{ti}"
        if not t.get("questions"):
            err("R2", tp, f"tab '{t.get('title')}' has no fields")
        for qi, q in enumerate(t.get("questions") or []):
            s, sp = q["field"], f"{tp}/questions/{qi}/field"
            if s["type"] not in SECTIONS:
                err("R2", sp, f"'{s.get('techName')}' on tab '{t.get('title')}' is not inside a section")
                continue
            for ci, c in enumerate(s.get("repeatingSectionGrid") or []):
                f, fp = c["field"], f"{sp}/repeatingSectionGrid/{ci}/field"
                techs.setdefault(f.get("techName"), []).append(fp)
                index[(t.get("title"), s.get("techName"), f.get("techName"))] = f
                if f["type"] in SECTIONS:
                    err("R2", fp, f"nested section '{f.get('techName')}'")
                if t.get("type") == "FINISH" and f["type"] in INPUT | {"CONSENT_SECTION"}:
                    err("R3", fp, f"input field '{f.get('techName')}' on the FINISH tab")
                if f["type"] in INPUT and not isinstance(f.get("validation"), list):
                    err("R4", f"{fp}/validation", f"'{f.get('techName')}' validation is not a list")
                elif f.get("readOnly") and "REQUIRED" in f["validation"] and f.get("defaultValue") in (None, "", []):
                    err("readOnly", fp, f"'{f.get('techName')}' is read-only and required but has no value: the form cannot be sent")
                if f["type"] in ("SELECT", "RADIO", "CHECKBOX") and not (f.get("options") or f.get("dictionaryName")):
                    err("choice", fp, f"choice field '{f.get('techName')}' has neither options nor dictionaryName")
                if f.get("dictionaryName") and f.get("options"):
                    err("choice", fp, f"'{f.get('techName')}' has both dictionaryName and options")
    for k, paths in techs.items():
        if len(paths) > 1:
            err("techName", paths[1], f"techName '{k}' is used {len(paths)} times")
    ids = [t.get("id") for t in tabs]
    chain = [(link.get("source"), link.get("target")) for link in (form.get("flow") or {}).get("links") or []]
    if any(a not in ids or b not in ids for a, b in chain) or (len(ids) > 1 and {i for link in chain for i in link} != set(ids)):
        err("R5", "/flow/links", "flow links do not connect all tabs")
    for ti, t in enumerate(tabs):  # R6: every JSONata reference resolves, compared values are real options
        for qi, q in enumerate(t.get("questions") or []):
            nodes = [(f"/tabs/{ti}/questions/{qi}/field", q["field"])]
            nodes += [(f"/tabs/{ti}/questions/{qi}/field/repeatingSectionGrid/{ci}/field", c["field"])
                      for ci, c in enumerate(q["field"].get("repeatingSectionGrid") or [])]
            for path, node in nodes:
                for si, st in enumerate(node.get("states") or []):
                    for val, page, sec, f1, f2 in REF.findall(st.get("query") or ""):
                        page, val = page.replace("\\'", "'"), json.loads(f'"{val}"') if val else val
                        target = index.get((page, sec, f1 or f2))
                        if target is None:
                            err("R6", f"{path}/states/{si}", f"'{node.get('techName')}' refers to missing {page}/{sec}/{f1 or f2}")
                        elif val and target.get("options") and val not in [o.get("name") for o in target["options"]]:
                            err("R6", f"{path}/states/{si}", f"'{node.get('techName')}' compares with '{val}', not an option of {f1 or f2}")
