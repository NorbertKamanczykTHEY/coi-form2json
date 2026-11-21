"""Thin OpenAI-compatible client: Eden AI today, a local vLLM/Ollama tomorrow (only LLM_BASE_URL and the model names change)."""
import time
from dataclasses import dataclass

from openai import OpenAI

from .config import Config


@dataclass
class Reply:
    text: str
    finish: str | None
    cost: float
    seconds: float


def client(cfg: Config) -> OpenAI:
    # api_key must be non-empty for the SDK; local servers ignore it
    return OpenAI(base_url=cfg.llm_base_url, api_key=cfg.llm_api_key or "none", max_retries=3, timeout=300)


def chat(c: OpenAI, model: str, content, max_tokens: int) -> Reply:
    t = time.perf_counter()
    r = c.chat.completions.create(model=model, temperature=0, max_tokens=max_tokens, messages=[{"role": "user", "content": content}])
    extra = (r.model_extra or {}) | ((r.usage and r.usage.model_extra) or {})  # Eden reports cost outside the OpenAI schema
    ch = r.choices[0]
    return Reply(ch.message.content or "", ch.finish_reason, float(extra.get("cost") or 0.0), time.perf_counter() - t)
