"""A slow LLM call fails one rung of a ladder (bounded wait, one retry) and the ladder escalates instead of ending the request."""
from pathlib import Path

import httpx2
import openai

from coi import llm
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
    assert client.timeout == 7 and client.max_retries == 1


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
