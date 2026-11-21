"""File -> COI form: parse -> extract -> generate. The one seam the API calls."""
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass

from .config import Config
from .extraction.anchors import blocks_of
from .extraction.extract import extract
from .extraction.tree import FieldTree
from .generator import generate
from .parsing import parse

OnEvent = Callable[[str, dict], None]  # (event, payload): "stage" | "escalation" | "warning"


@dataclass
class Result:
    form: dict  # pure COI JSON, importable as is
    report: dict  # trace, warnings, needs_review, cost, seconds, proposed_dictionaries
    editor: dict  # source (ParsedDocument), field_map (fieldId -> page, block, bbox, confidence, needs_review)


def convert(data: bytes, filename: str, on_event: OnEvent = lambda *_: None, cfg: Config | None = None, store=None) -> Result:
    """`store` (coi.store.Store) lets the generator match dictionaries; without it fields keep their own options."""
    t0 = time.perf_counter()
    on_event("stage", {"stage": "parse", "status": "start"})
    doc = parse(data, filename, cfg)
    # shortcut: parse() has no progress hook, so escalations are replayed from the trace after the fact; add a callback to parse() for live events
    for e in doc.trace:
        if str(e.get("step", "")).startswith("VLM"):
            on_event("escalation", {k: e.get(k) for k in ("page", "step", "model", "accepted", "error")})
    for w in doc.warnings:
        on_event("warning", {"message": w})
    on_event("stage", {"stage": "parse", "status": "done", "seconds": doc.source.get("seconds"), "parser": doc.source.get("parser")})

    on_event("stage", {"stage": "extract", "status": "start"})
    ex = extract(doc, on_event)
    on_event("stage", {"stage": "extract", "status": "done", "cost": ex.cost})

    on_event("stage", {"stage": "generate", "status": "start"})
    form, parts, field_map = generate(ex.tree, hashlib.sha256(data).hexdigest(), on_event, store, blocks=blocks_of(doc),
                                      extra_review=ex.needs_review)
    on_event("stage", {"stage": "generate", "status": "done", "fields": len(field_map)})

    report = {
        "trace": doc.trace + ex.trace,
        "warnings": doc.warnings + parts["warnings"],
        "needs_review": parts["needs_review"],  # extraction's and generator's, each naming a field (key, field_id)
        "proposed_dictionaries": parts["proposed_dictionaries"],
        "validation": parts["validation"],
        "cost": round(doc.source.get("cost", 0) + ex.cost, 5),
        "seconds": round(time.perf_counter() - t0, 2),
        "source": doc.source,
    }
    # tree + raw extraction review + parse warnings: enough to rebuild the form without the LLM (regenerate)
    editor = {"source": doc.to_dict(), "field_map": field_map, "proposals": parts["editor_proposals"],
              "applicant_self_only": parts["applicant_self_only"], "tree": ex.tree.model_dump(mode="json"),
              "extraction_review": ex.needs_review, "parse_warnings": doc.warnings}
    return Result(form, report, editor)


class NoStoredTree(LookupError):
    """The form was stored before FieldTree was kept in `editor.tree`: it cannot be rebuilt without a new conversion."""


def regenerate(row: dict, store=None, applicant_self_only: bool | None = None) -> Result:
    """Stored form -> the same form rebuilt from its FieldTree with the editor's overrides; no parsing, no LLM."""
    ed = row["editor"]
    if not ed.get("tree"):
        raise NoStoredTree(row["id"])
    blocks = {f"p{p['number']}.b{i}": b["text"] for p in ed["source"]["pages"] for i, b in enumerate(p["blocks"])}
    form, parts, field_map = generate(FieldTree.model_validate(ed["tree"]), row["sha256"], None, store, blocks=blocks,
                                      extra_review=ed.get("extraction_review"), applicant_self_only=applicant_self_only)
    report = row["report"] | {"warnings": ed.get("parse_warnings", []) + parts["warnings"], "needs_review": parts["needs_review"],
                              "proposed_dictionaries": parts["proposed_dictionaries"], "validation": parts["validation"]}
    editor = ed | {"field_map": field_map, "proposals": parts["editor_proposals"], "applicant_self_only": parts["applicant_self_only"]}
    return Result(form, report, editor)
