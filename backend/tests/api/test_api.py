import io
import json
from pathlib import Path

import pytest

from coi import create_app, pipeline
from coi.extraction.extract import ExtractionResult
from coi.extraction.tree import FieldTree
from coi.make_token import make

ROOT = Path(__file__).resolve().parents[4]
MAT = ROOT / "materials"
FORM1 = next(MAT.glob("1. *"))
DOCX = next(p for p in FORM1.glob("*.docx") if "wizualizacja" not in p.name)
PDF = next(FORM1.glob("*.pdf"))
JPE = next(next(MAT.glob("7. *")).glob("*.JPE"))
SECRET = "test-secret-at-least-32-bytes-long!!"
# offline: extraction (LLM) is replaced by the recorded FieldTree of #1; parse and generate run for real
TREE1 = FieldTree.model_validate_json((Path(__file__).parents[1] / "generator/fixtures/form1.tree.json").read_text())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("JWT_ALG", "HS256")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'coi.sqlite'}")
    monkeypatch.setenv("MAX_FILE_MB", "5")
    for k in ("JWT_ISSUER", "JWT_AUDIENCE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(pipeline, "extract", lambda doc, on_event=None: ExtractionResult(TREE1, [], [{"stage": "extract"}], 0.01))
    return create_app().test_client()


H = {"Authorization": f"Bearer {make(SECRET, 'tester')}"}


def upload(client, data: bytes, name: str, query: str = "", headers=None):
    return client.post(f"/api/v1/forms{query}", data={"file": (io.BytesIO(data), name)}, headers=headers or H, content_type="multipart/form-data")


@pytest.fixture(scope="module")
def docx() -> bytes:
    return DOCX.read_bytes()


def test_public_endpoints(client):
    assert client.get("/healthz").json == {"status": "ok"}
    info = client.get("/api/v1/info").json
    assert info["limits"]["max_file_mb"] == 5 and "docx" in info["limits"]["extensions"]
    assert client.get("/openapi.json").json["paths"]["/api/v1/forms"]
    assert client.get("/docs").status_code == 200


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nope"}, {"Authorization": f"Bearer {make('other-secret-that-is-long-enough!!', 'x')}"},
                                     {"Authorization": f"Bearer {make(SECRET, 'x', hours=-1)}"}])
def test_401(client, headers):
    r = client.get("/api/v1/forms", headers=headers)
    assert r.status_code == 401
    assert r.content_type == "application/problem+json" and r.json["status"] == 401 and r.json["code"]


@pytest.mark.parametrize("name", ["a;b.docx", "a:b.docx", "x" * 247 + ".docx", "a%b.docx", "a$b.docx", "a'b.docx"])
def test_400_bad_name(client, name):
    r = upload(client, b"x", name)
    assert r.status_code == 400 and r.json["code"] == "invalid_filename"


def test_400_no_file_and_two_files(client, docx):
    assert client.post("/api/v1/forms", headers=H, data={}, content_type="multipart/form-data").status_code == 400
    r = client.post("/api/v1/forms", headers=H, content_type="multipart/form-data",
                    data={"file": [(io.BytesIO(docx), "a.docx"), (io.BytesIO(docx), "b.docx")]})
    assert r.status_code == 400


def test_413(client):
    assert upload(client, b"%PDF" + b"0" * (5 * 2**20), "big.pdf").status_code == 413  # over MAX_FILE_MB, under MAX_CONTENT_LENGTH
    r = upload(client, b"0" * (6 * 2**20), "huge.pdf")  # over MAX_CONTENT_LENGTH: rejected by Werkzeug
    assert r.status_code == 413 and r.content_type == "application/problem+json"


def test_415(client):
    assert upload(client, JPE.read_bytes(), JPE.name).status_code == 415
    r = upload(client, PDF.read_bytes(), "renamed.png")
    assert r.status_code == 415 and r.json["code"] == "unsupported_type"


def test_convert_docx_store_and_read(client, docx):
    r = upload(client, docx, "Wniosek 1.docx")
    assert r.status_code == 200
    form = r.json
    assert form["title"] == TREE1.title and [t["type"] for t in form["tabs"]] == ["MAIN", "MAIN", "MAIN", "FINISH"]
    assert client.post("/api/v1/forms/validate", json=form, headers=H).json == {"valid": True, "errors": []}
    fid = r.headers["Location"].rsplit("/", 1)[1]

    items = client.get("/api/v1/forms", headers=H).json["items"]
    assert [(i["id"], i["created_by"], i["filename"]) for i in items] == [(fid, "tester", "Wniosek 1.docx")]
    assert client.get(f"/api/v1/forms/{fid}", headers=H).json == form
    env = client.get(f"/api/v1/forms/{fid}?report=true&editor=true", headers=H).json
    assert env["form"] == form and env["editor"]["source"]["pages"]
    assert client.get("/api/v1/forms/missing", headers=H).status_code == 404


def test_report_and_editor(client, docx):
    r = upload(client, docx, "w.docx", "?report=true").json
    assert set(r) == {"id", "form", "report"} and {"trace", "warnings", "needs_review", "cost"} <= set(r["report"])
    r = upload(client, docx, "w.docx", "?editor=true").json
    fmap = r["editor"]["field_map"]
    assert r["editor"]["source"]["pages"][0]["blocks"] and fmap and all(m["src"] for m in fmap.values())


def test_sse(client, docx):
    r = upload(client, docx, "w.docx", headers=H | {"Accept": "text/event-stream"})
    assert r.status_code == 200 and r.mimetype == "text/event-stream"
    events = [dict(line.split(": ", 1) for line in chunk.splitlines()) for chunk in r.get_data(as_text=True).strip().split("\n\n")]
    kinds = [e["event"] for e in events]
    assert kinds[0] == "stage" and kinds[-1] == "result"
    assert json.loads(events[0]["data"]) == {"stage": "parse", "status": "start"}
    assert json.loads(events[-1]["data"])["tabs"] and events[-1]["id"]


def test_sse_error_event(client):
    r = upload(client, b"not a pdf", "x.pdf", headers=H | {"Accept": "text/event-stream"})
    last = r.get_data(as_text=True).strip().split("\n\n")[-1]
    assert last.startswith("event: error") and '"status": 415' in last


def test_put_validates(client, docx):
    fid = upload(client, docx, "w.docx", "?report=true").json["id"]
    bad = client.put(f"/api/v1/forms/{fid}", json={"title": 5, "tabs": []}, headers=H)
    assert bad.status_code == 422 and bad.json["errors"][0]["path"] == "/title"
    rules = client.put(f"/api/v1/forms/{fid}", json={"title": "Poprawiony", "tabs": [], "flow": {"links": []}}, headers=H)
    assert rules.status_code == 422 and rules.json["errors"][0]["rule"] == "R1"
    good = client.get(f"/api/v1/forms/{fid}", headers=H).json | {"title": "Poprawiony"}
    assert client.put(f"/api/v1/forms/{fid}", json=good, headers=H).json == good
    assert client.get(f"/api/v1/forms/{fid}", headers=H).json == good
    assert client.get("/api/v1/forms", headers=H).json["items"][0]["updated_by"] == "tester"
    assert client.put("/api/v1/forms/missing", json=good, headers=H).status_code == 404


def test_regenerate_without_llm(client, docx):
    body = upload(client, docx, "w.docx", "?editor=true").json
    fid = body["id"]
    assert body["editor"]["applicant_self_only"] == {"value": False, "source": "domyślnie", "quote": None} and body["editor"]["tree"]
    calls = []
    pipeline.extract = lambda *a, **k: calls.append(1)  # must not be called
    r = client.post(f"/api/v1/forms/{fid}/regenerate?editor=true", json={"applicant_self_only": True}, headers=H)
    assert r.status_code == 200 and not calls
    techs = {c["field"]["techName"] for t in r.json["form"]["tabs"] for q in t["questions"] for c in q["field"]["repeatingSectionGrid"]}
    assert "dokument_z_potwierdzeniem_podpisany_elektronicznie" not in techs
    assert r.json["editor"]["applicant_self_only"]["source"] == "edytor"
    assert client.get(f"/api/v1/forms/{fid}", headers=H).json == r.json["form"]
    assert client.post("/api/v1/forms/validate", json=r.json["form"], headers=H).json["valid"]
    assert client.post(f"/api/v1/forms/{fid}/regenerate", json={}, headers=H).status_code == 400
    assert client.post("/api/v1/forms/missing/regenerate", json={"applicant_self_only": True}, headers=H).status_code == 404
    old = client.application.config["STORE"].add_form(filename="a", sha256="0" * 64, user="t", form=r.json["form"], report={}, editor={})
    gone = client.post(f"/api/v1/forms/{old}/regenerate", json={"applicant_self_only": True}, headers=H)
    assert gone.status_code == 409 and gone.json["code"] == "no_stored_tree"
    assert "/api/v1/forms/{form_id}/regenerate" in client.get("/openapi.json").json["paths"]
