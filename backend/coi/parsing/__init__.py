"""File parsing: the only public entry is parse(). Raises TooLarge (413), UnsupportedType (415); Kreuzberg errors on broken files propagate."""
from ..config import Config
from .detect import TooLarge, UnsupportedType
from .markdown import to_markdown
from .model import Block, Kind, Page, ParsedDocument
from .pipeline import run

__all__ = ["parse", "to_markdown", "ParsedDocument", "Page", "Block", "Kind", "TooLarge", "UnsupportedType"]


def parse(data: bytes, filename: str, cfg: Config | None = None) -> ParsedDocument:
    return run(data, filename, cfg or Config.load())
