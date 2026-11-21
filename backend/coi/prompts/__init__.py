"""All LLM/VLM prompts live here as .md files; code only loads them and fills {placeholders}."""
from functools import cache
from pathlib import Path

DIR = Path(__file__).resolve().parent


@cache
def _read(name: str) -> str:
    return (DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def prompt(name: str, **values) -> str:
    text = _read(name)
    return text.format(**values) if values else text
