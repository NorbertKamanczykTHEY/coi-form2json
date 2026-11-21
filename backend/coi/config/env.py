"""Raw settings source: the process environment, with app/.env filling what it lacks (local runs; Docker uses env_file)."""
import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"  # app/.env


def env() -> dict[str, str]:
    values = {}
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text().splitlines():
            k, sep, v = line.partition("=")
            if sep and not k.lstrip().startswith("#"):
                values[k.strip()] = v.strip().strip("'\"")
    return values | dict(os.environ)
