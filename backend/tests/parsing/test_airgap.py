"""LLM_PROVIDER=local: VLM calls go only to the local server, never to Eden, and no Eden key is needed or sent."""
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from coi import llm
from coi.config import Config
from coi.parsing import ParserEnvironmentError, parse

from .conftest import FILES

PNG = next(p for f, p in FILES if f == "form7" and p.suffix == ".PNG")


class Stub(BaseHTTPRequestHandler):
    calls: list[dict] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Stub.calls.append({"path": self.path, "auth": self.headers.get("Authorization"), "model": body["model"],
                           "response_format": body.get("response_format")})
        out = json.dumps({"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                          "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "# STUB"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture
def local_server(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    hosts = []
    real = socket.getaddrinfo
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *a, **k: hosts.append(host) or real(host, *a, **k))
    monkeypatch.setenv("LLM_PROVIDER", "local")
    monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{srv.server_port}/v1")
    monkeypatch.setenv("EDENAI_API_KEY", "")  # overrides app/.env
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LADDER_PATH", raising=False)
    Stub.calls = []
    yield hosts
    srv.shutdown()


def test_local_provider_never_calls_eden(local_server):
    events = []
    doc = parse(PNG.read_bytes(), PNG.name, Config.load(), lambda ev, p: events.append((ev, p)))
    assert Stub.calls, "the scan page must have escalated to the local VLM"
    assert {c["model"] for c in Stub.calls} == {"qwen3-vl:8b"}  # ladder.local.json
    assert all(c["path"] == "/v1/chat/completions" and c["auth"] == "Bearer none" for c in Stub.calls)
    assert local_server and all(h == "127.0.0.1" for h in local_server), local_server
    assert ("escalation" in {e for e, _ in events}) and doc.source["cost"] == 0


def test_eden_without_key_is_an_environment_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "eden")
    monkeypatch.setenv("EDENAI_API_KEY", "")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ParserEnvironmentError):
        parse(PNG.read_bytes(), PNG.name, Config.load())


def test_response_format_reaches_the_provider(local_server):
    fmt = {"type": "json_schema", "json_schema": {"name": "f", "schema": {"type": "object"}, "strict": True}}
    llm.provider(Config.load()).chat("m", "hi", 10, response_format=fmt)
    llm.provider(Config.load()).chat("m", "hi", 10)
    assert [c["response_format"] for c in Stub.calls] == [fmt, None]
