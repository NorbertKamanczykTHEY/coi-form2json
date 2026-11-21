"""Settings from the environment; app/.env fills in what the environment lacks (local runs). Docker passes env_file instead."""
import os
from dataclasses import dataclass
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"  # app/.env
DEFAULT_LADDER = Path(__file__).resolve().parent / "parsing" / "ladder.json"


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
    llm_base_url: str
    llm_api_key: str
    ladder_path: Path

    @classmethod
    def load(cls) -> "Config":
        e = _env()
        return cls(
            max_file_mb=float(e.get("MAX_FILE_MB", "20")),
            llm_base_url=e.get("LLM_BASE_URL", "https://api.edenai.run/v3"),
            llm_api_key=e.get("LLM_API_KEY") or e.get("EDENAI_API_KEY", ""),
            ladder_path=Path(e.get("LADDER_PATH") or DEFAULT_LADDER),
        )
