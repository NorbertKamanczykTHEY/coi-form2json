"""File -> COI form. The one seam the API calls; the generator plugs in here later without touching the API."""
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePath

from .config import Config
from .parsing import parse

OnEvent = Callable[[str, dict], None]  # (event, payload): "stage" | "escalation" | "warning"


@dataclass
class Result:
    form: dict  # pure COI JSON, importable as is
    report: dict  # trace, warnings, needs_review, cost, seconds, proposed_dictionaries
    editor: dict  # source (ParsedDocument), field_map (fieldId -> page, block, bbox, confidence, needs_review)


def _stub_form(title: str) -> dict:
    main, finish = str(uuid.uuid4()), str(uuid.uuid4())
    return {
        "title": title,
        "tabs": [
            {"id": main, "title": "Dane", "type": "MAIN", "questions": []},
            {"id": finish, "title": "Strona końcowa", "type": "FINISH", "questions": []},
        ],
        "flow": {"links": [{"id": str(uuid.uuid4()), "source": main, "target": finish}]},
    }


def convert(data: bytes, filename: str, on_event: OnEvent = lambda *_: None, cfg: Config | None = None) -> Result:
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

    on_event("stage", {"stage": "generate", "status": "start"})
    # shortcut: no generator yet, the form is a valid empty MAIN + FINISH skeleton titled from the filename; the real generator replaces this block
    form = _stub_form(PurePath(filename).stem)
    on_event("stage", {"stage": "generate", "status": "done"})

    report = {
        "trace": doc.trace,
        "warnings": doc.warnings,
        "needs_review": [],
        "proposed_dictionaries": [],
        "cost": doc.source.get("cost", 0),
        "seconds": round(time.perf_counter() - t0, 2),
        "source": doc.source,
    }
    return Result(form, report, {"source": doc.to_dict(), "field_map": {}})
