"""LLM/VLM provider adapter (ADR 10). Callers see only Provider.chat(); LLM_PROVIDER picks the implementation.

eden:  Eden AI, OpenAI-compatible, needs EDENAI_API_KEY (or LLM_API_KEY), reports cost.
local: any OpenAI-compatible server on the internal network (vLLM, Ollama). Air gap: no Eden URL, no Eden key.
"""
import time
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from .config import Config

EDEN_URL = "https://api.edenai.run/v3"
LOCAL_URL = "http://localhost:11434/v1"  # Ollama default; vLLM: http://<host>:8000/v1


class LLMConfigError(RuntimeError):
    """Provider misconfigured (e.g. no key): an environment problem, not a problem with the uploaded file."""


@dataclass
class Reply:
    text: str
    finish: str | None
    cost: float
    seconds: float


class Provider(Protocol):
    name: str

    def chat(self, model: str, content: str | list, max_tokens: int, response_format: dict | None = None) -> Reply:
        """response_format: OpenAI style, e.g. {"type": "json_schema", "json_schema": {"name": ..., "schema": {...}, "strict": True}}"""
        ...


class OpenAICompatible:
    def __init__(self, name: str, base_url: str, api_key: str):
        self.name = name
        self.base_url = base_url
        # the SDK wants a non-empty key; local servers ignore it
        self._client = OpenAI(base_url=base_url, api_key=api_key or "none", max_retries=3, timeout=300)

    def chat(self, model: str, content: str | list, max_tokens: int, response_format: dict | None = None) -> Reply:
        t = time.perf_counter()
        kw = {"response_format": response_format} if response_format else {}
        r = self._client.chat.completions.create(model=model, temperature=0, max_tokens=max_tokens,
                                                 messages=[{"role": "user", "content": content}], **kw)
        meta = (r.model_extra or {}) | ((r.usage and r.usage.model_extra) or {})  # Eden reports cost outside the OpenAI schema
        ch = r.choices[0]
        return Reply(ch.message.content or "", ch.finish_reason, float(meta.get("cost") or 0.0), time.perf_counter() - t)


def provider(cfg: Config) -> Provider:
    if cfg.llm_provider == "local":
        return OpenAICompatible("local", cfg.llm_base_url or LOCAL_URL, cfg.llm_api_key)
    key = cfg.llm_api_key or cfg.eden_api_key
    if not key:
        raise LLMConfigError("LLM_PROVIDER=eden needs EDENAI_API_KEY (or set LLM_PROVIDER=local for a local server)")
    return OpenAICompatible("eden", cfg.llm_base_url or EDEN_URL, key)
