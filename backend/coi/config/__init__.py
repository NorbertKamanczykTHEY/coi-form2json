"""All settings in one place, one module per area (Laravel-style config/): app, llm, parsing; auth, database,
dictionaries, generator are added by their owners. Each module has load() -> dict, reading env with defaults.

    from coi.config import config
    config("llm.provider")            # one value
    config("parsing")                 # the whole area

Values are read on every call, so env changes (tests, reloads) apply without restarts.
"""
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from .env import ENV_FILE, env

_env = env  # older call sites: from .config import _env

__all__ = ["config", "env", "Config", "ENV_FILE"]
_MISSING = object()


def config(key: str, default=_MISSING):
    area, _, name = key.partition(".")
    values = import_module(f"{__name__}.{area}").load()
    if not name:
        return values
    if name in values:
        return values[name]
    if default is _MISSING:
        raise KeyError(f"no setting {key!r}")
    return default


@dataclass(frozen=True)
class Config:
    """Snapshot of the settings parse() and the LLM provider need; pass one around instead of re-reading env."""
    max_file_mb: float
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    eden_api_key: str
    ladder_path: Path
    tessdata: str = ""
    llm_timeout_s: float = 90.0

    @classmethod
    def load(cls) -> "Config":
        llm = config("llm")
        return cls(max_file_mb=config("app.max_file_mb"), llm_provider=llm["provider"], llm_base_url=llm["base_url"],
                   llm_api_key=llm["api_key"], eden_api_key=llm["eden_api_key"], ladder_path=config("parsing.ladder_path"),
                   tessdata=config("parsing.tessdata"), llm_timeout_s=llm["timeout_s"])
