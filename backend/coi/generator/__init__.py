"""FieldTree -> COI JSON, deterministic and without LLM. Design: app/docs/design/generator.md.

    form, report_parts, field_map = generate(tree, source_sha256, on_event, store)
"""
from collections.abc import Callable

from ..config import config
from ..extraction.tree import FieldTree
from .adapter import load_presets, to_internal
from .build import build, stable_id
from .validate import validate

try:
    from ..dictionaries import canonical, match
except ImportError:  # shortcut: coi.dictionaries not committed yet -> no dictionary matching, local alias map; drop once it lands
    match = None

    def canonical(name: str) -> str:
        return {"TERYT_DOWODOWY": "TERYT_4G_DOWODOWY"}.get(name, name)

__all__ = ["generate", "validate"]
DICT_TYPES = ("SELECT", "CHECKBOX", "TEXT_FIELD")  # RADIO keeps its options in the field, as all 7 RADIOs in the patterns
# a TEXT_FIELD keeps free text for these: phone prefix is a separate SELECT (generator.md pkt 5), address parts stay text as in #1
TEXT_STAYS = {"NUMERY_KIERUNKOWE", "WOJEWODZTWO", "POWIAT", "GMINA", "MIEJSCOWOSC", "TERYT_4G_DOWODOWY"}


def _matcher(session, proposals: dict):
    """Only existing dictionaries change the field (ADR 0025); a proposal leaves it as is and is collected for the report."""
    def dictionary(f: dict) -> dict | None:
        if f["type"] not in DICT_TYPES or f.get("from_preset"):
            return None
        m = match(session, f.get("label") or "", f["meta"].get("source_label", ""), f["type"], f.get("options") or [])
        if m is None or (f["type"] == "TEXT_FIELD" and canonical(m.dictionaryName) in TEXT_STAYS):
            return None
        if m.proposal and m.proposal.get("source") == "document" and f["type"] != "SELECT":  # dictionaries from the paper: SELECT only
            return None
        change = {"type": m.component, "dictionaryName": canonical(m.dictionaryName), "options": [],
                  "multiLevelTree": m.multiLevelTree, "searchEnabled": m.searchEnabled}
        if m.decision == "new":
            p = proposals.setdefault(m.proposal["id"], {"proposal": {**m.proposal, "fields": []}, "changes": {}})
            p["proposal"]["fields"].append(f["tech"])
            p["changes"][f["tech"]] = change
            f["meta"]["needs_review"] = True
        else:
            f.pop("options", None)
            f |= {"type": change["type"], "dictionary": change["dictionaryName"], "multi_level": m.multiLevelTree, "search": m.searchEnabled}
        return {"name": change["dictionaryName"], "decision": m.decision, "score": m.score, "reason": m.reason}
    return dictionary


def _canonical_names(form: dict) -> None:
    """Q22: every dictionaryName (templates included) leaves under its canonical name."""
    for t in form["tabs"]:
        for q in t["questions"]:
            for c in q["field"]["repeatingSectionGrid"]:
                if name := c["field"].get("dictionaryName"):
                    c["field"]["dictionaryName"] = canonical(name)


def generate(tree: FieldTree, source_sha256: str, on_event: Callable[[str, dict], None] | None = None, store=None,
             settings: dict | None = None, blocks: dict[str, str] | None = None) -> tuple[dict, dict, dict]:
    """-> (COI form, report parts {warnings, needs_review, proposed_dictionaries, validation, editor_proposals},
    field_map fieldId -> src/review). editor_proposals: per proposal the body for POST /dictionaries/from-proposal,
    the fields it concerns and the ready field change the editor applies on acceptance.
    `store` (coi.store.Store) enables dictionary matching; `settings` overrides config('generator') (tests);
    `blocks` (coi.extraction.anchors.blocks_of) gives the source text behind the tree's anchors."""
    on_event = on_event or (lambda *_: None)
    s = config("generator") | (settings or {})
    internal, warnings, review = to_internal(tree, s, load_presets(s["templates"]), blocks)
    proposals: dict = {}
    if store is not None and match is not None:
        with store.session() as session:
            form, more, field_map = build(internal, source_sha256, s["templates"], _matcher(session, proposals))
    else:
        form, more, field_map = build(internal, source_sha256, s["templates"])
    _canonical_names(form)
    warnings += more
    review += [{"field_id": fid, "key": m["techName"], "why": m.get("doubt") or f"propozycja słownika {m['dictionary']['name']}"} for fid, m in field_map.items() if m["needs_review"]]
    errors = validate(form)
    warnings += [f"walidator: {e['rule']} {e['path']}: {e['message']}" for e in errors]
    for w in warnings:
        on_event("warning", {"message": w})
    editor = []
    for p in proposals.values():
        changes = {fid: c for t, c in p["changes"].items() if (fid := stable_id(source_sha256, "field", t)) in field_map}  # field may be pruned
        editor.append({"dictionary": p["proposal"], "fieldIds": list(changes), "changes": changes})
    return form, {"warnings": warnings, "needs_review": review, "proposed_dictionaries": [p["proposal"] for p in proposals.values()],
                  "validation": errors, "editor_proposals": editor}, field_map
