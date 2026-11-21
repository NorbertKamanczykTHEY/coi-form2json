"""E2E on the running container: POST /api/v1/forms?report=true for every form, /forms/validate, schema from materials/.

usage (from app/backend, stack up via `docker compose up`): uv run python ../results/run.py [name ...]
Writes <name>.coi.json (pure COI JSON), <name>.report.json and summary.json next to this file.
"""
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import jsonschema

from coi.config import env
from coi.make_token import make

OUT = Path(__file__).resolve().parent
MAT = OUT.parents[1] / "materials"
API = "http://localhost:8000/api/v1"
SCHEMA = jsonschema.Draft202012Validator(json.loads(next(MAT.glob("Materiały*/importowanyPlikJsonSchemat*.json")).read_text()))
# name -> (material folder number, file suffix): the editable original (docx; #7 has only .DOC), plus scans for the VLM path
RUNS = {
    "1-numer-porzadkowy": (1, ".docx"), "2-zwrot-oplaty-skarbowej": (2, ".docx"), "3-zaswiadczenie": (3, ".docx"),
    "4-swietlica": (4, ".docx"), "5-nadplata-podatku": (5, ".docx"), "6-pas-drogowy": (6, ".docx"),
    "7-psy-agresywne": (7, ".DOC"), "8-deklaracja-odpady": (8, ".docx"), "9-stypendium-sportowe": (9, ".docx"),
    "7-psy-agresywne-skan": (7, ".JPG"), "9-stypendium-sportowe-skan": (9, ".png"),
}
TOKEN = make(env()["JWT_SECRET"], "e2e-results")


def call(path: str, body: bytes, ctype: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"{API}{path}", body, {"Authorization": f"Bearer {TOKEN}", "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def upload(f: Path) -> tuple[int, dict]:
    b = uuid.uuid4().hex
    head = f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{f.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    return call("/forms?report=true", head.encode() + f.read_bytes() + f"\r\n--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}")


def main(names):
    summary = json.loads((OUT / "summary.json").read_text()) if (OUT / "summary.json").exists() else {}
    for name in names:
        n, suffix = RUNS[name]
        f = next(p for p in next(MAT.glob(f"{n}. *")).iterdir() if p.suffix == suffix and "wizualizacja" not in p.name)
        t0 = time.time()
        status, body = upload(f)
        row = {"file": f.name, "format": suffix.lstrip(".").lower(), "seconds": round(time.time() - t0, 1), "status": status}
        if status == 200:
            form, rep = body["form"], body["report"]
            (OUT / f"{name}.coi.json").write_text(json.dumps(form, ensure_ascii=False, indent=1))
            (OUT / f"{name}.report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
            _, v = call("/forms/validate", json.dumps(form).encode(), "application/json")
            fields = sum(len(q["field"]["repeatingSectionGrid"]) for t in form["tabs"] for q in t["questions"])
            row |= {"cost": rep["cost"], "fields": fields, "needs_review": len(rep["needs_review"]), "warnings": len(rep["warnings"]),
                    "valid": v["valid"], "errors": v["errors"][:5], "schema_errors": [e.message for e in SCHEMA.iter_errors(form)][:5],
                    "proposed": [p["id"] for p in rep["proposed_dictionaries"]], "title": form["title"],
                    "pages": [t["title"] for t in form["tabs"]]}
        else:
            row["error"] = body
        summary[name] = row
        (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
        print(name, json.dumps({k: row.get(k) for k in ("status", "seconds", "cost", "fields", "needs_review", "valid")}), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or list(RUNS))
