from pathlib import Path

from . import llm
from .env import env

PARSING = Path(__file__).resolve().parents[1] / "parsing"
LADDERS = {"eden": PARSING / "ladder.json", "local": PARSING / "ladder.local.json"}


def load() -> dict:
    e = env()
    return {
        "ladder_path": Path(e.get("LADDER_PATH") or LADDERS[llm.load()["provider"]]),  # VLM tiers + gate thresholds
        "tessdata": e.get("TESSDATA_PREFIX", ""),  # empty = Tesseract's built-in path (Docker: apt tesseract-ocr-pol)
    }
