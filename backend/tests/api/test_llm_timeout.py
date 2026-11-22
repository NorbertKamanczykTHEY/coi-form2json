"""A slow LLM call fails one rung of a ladder (bounded wait, one retry) and the ladder escalates instead of ending the request."""
import dataclasses
import io
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx2
import openai
import pytest

from coi import create_app, llm
from coi.make_token import make
from coi.config import Config
from coi.extraction.extract import extract
from coi.llm import Reply
from coi.parsing import parse

FIX = Path(__file__).parents[1] / "generator/fixtures/form1.tree.json"
DOCX = next(p for p in next((Path(__file__).resolve().parents[4] / "materials").glob("1. *")).glob("*.docx") if "wizualizacja" not in p.name)


def test_client_timeout_from_config(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_S", "7")
    monkeypatch.setenv("EDENAI_API_KEY", "k")
    client = llm.provider(Config.load())._client
    assert client.timeout.read == 7 and client.timeout.connect == 7 and client.max_retries == 1


class SlowFirst:
    name = "fake"

    def __init__(self):
        self.models = []

    def chat(self, model, content, max_tokens, response_format=None):
        self.models.append(model)
        if model == "slow":
            raise openai.APITimeoutError(request=httpx2.Request("POST", "http://x"))
        return Reply(FIX.read_text(), "stop", 0.001, 0.1)


def test_extraction_timeout_escalates_to_next_rung(monkeypatch):
    monkeypatch.setenv("EXTRACTION_LADDER", "slow,fast")
    events = []
    p = SlowFirst()
    r = extract(parse(DOCX.read_bytes(), DOCX.name), lambda e, d: events.append((e, d)), provider=p)
    assert r.tree.title and p.models[0] == "slow" and "fast" in p.models
    assert r.trace[0]["rung"] == 0 and "APITimeoutError" in r.trace[0]["error"]
    assert ("escalation", {"step": "extract.0", "model": "slow", "accepted": False, "error": "slow: APITimeoutError"}) in events


class Slow(BaseHTTPRequestHandler):
    """An LLM server that accepts the connection and never answers in time."""

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        time.sleep(5)

    def log_message(self, *a):
        pass


@pytest.fixture
def slow_server(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("LLM_PROVIDER", "local")
    monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{srv.server_port}/v1")
    monkeypatch.setenv("LLM_TIMEOUT_S", "1")
    yield
    srv.shutdown()
    srv.server_close()


def test_slow_server_call_is_cut_by_the_timeout(slow_server):
    t = time.monotonic()
    with pytest.raises(openai.APITimeoutError):
        llm.provider(Config.load()).chat("m", "hi", 10)
    assert time.monotonic() - t < 4  # two 1 s attempts plus the SDK's retry backoff, not the server's 5 s


def test_no_call_after_the_deadline():
    p = llm.provider(dataclasses.replace(Config.load(), llm_provider="local", deadline=time.monotonic()))
    with pytest.raises(llm.DeadlineExceeded):
        p.chat("m", "hi", 10)


def test_request_deadline_ends_the_conversion_with_504(slow_server, monkeypatch, tmp_path):
    """Every extraction rung hits the slow server; the whole request stops at REQUEST_TIMEOUT_S with a readable 504."""
    monkeypatch.setenv("LLM_TIMEOUT_S", "60")
    monkeypatch.setenv("REQUEST_TIMEOUT_S", "3")
    monkeypatch.setenv("JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("JWT_ALG", "HS256")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'coi.sqlite'}")
    for k in ("JWT_ISSUER", "JWT_AUDIENCE"):
        monkeypatch.delenv(k, raising=False)
    client = create_app().test_client()
    t = time.monotonic()
    r = client.post("/api/v1/forms", data={"file": (io.BytesIO(DOCX.read_bytes()), DOCX.name)}, content_type="multipart/form-data",
                    headers={"Authorization": f"Bearer {make('test-secret-at-least-32-bytes-long!!', 'tester')}"})
    assert time.monotonic() - t < 8
    assert r.status_code == 504 and r.json["code"] == "llm_timeout" and "REQUEST_TIMEOUT_S" in r.json["detail"]
