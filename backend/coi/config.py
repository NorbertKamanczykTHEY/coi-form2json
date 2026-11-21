"""Settings from the environment; app/.env fills in what the environment lacks (local runs). Docker passes env_file instead."""
import os
from dataclasses import dataclass
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"  # app/.env
PARSING = Path(__file__).resolve().parent / "parsing"
LADDERS = {"eden": PARSING / "ladder.json", "local": PARSING / "ladder.local.json"}


def _env() -> dict[str, str]:
    env = {}
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text().splitlines():
            k, sep, v = line.partition("=")
            if sep and not k.lstrip().startswith("#"):
                env[k.strip()] = v.strip().strip("'\"")
    return env | dict(os.environ)


@dataclass(frozen=True)
class Config:
    max_file_mb: float
    llm_provider: str  # eden | local (air gap: no outbound traffic, no Eden key)
    llm_base_url: str  # empty = the provider's default
    llm_api_key: str  # LLM_API_KEY; the eden provider falls back to EDENAI_API_KEY
    eden_api_key: str
    ladder_path: Path

    @classmethod
    def load(cls) -> "Config":
        e = _env()
        provider = e.get("LLM_PROVIDER", "eden").strip().lower()
        if provider not in LADDERS:
            raise ValueError(f"LLM_PROVIDER must be one of {sorted(LADDERS)}, got {provider!r}")
        return cls(
            max_file_mb=float(e.get("MAX_FILE_MB", "20")),
            llm_provider=provider,
            llm_base_url=e.get("LLM_BASE_URL", ""),
            llm_api_key=e.get("LLM_API_KEY", ""),
            eden_api_key=e.get("EDENAI_API_KEY", ""),
            ladder_path=Path(e.get("LADDER_PATH") or LADDERS[provider]),
        )
