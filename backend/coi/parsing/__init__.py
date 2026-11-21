"""File parsing: the only public entry is parse().

Raises TooLarge (413), UnsupportedType (415), ParserEnvironmentError (500: the server, not the file).
Kreuzberg ParsingError on a broken file propagates (422)."""
from ..config import Config
from .detect import ParserEnvironmentError, TooLarge, UnsupportedType
from .markdown import to_markdown
from .model import Block, Kind, Page, ParsedDocument
from .pipeline import OnEvent, run

__all__ = ["parse", "to_markdown", "ParsedDocument", "Page", "Block", "Kind", "TooLarge", "UnsupportedType", "ParserEnvironmentError", "OnEvent"]


def parse(data: bytes, filename: str, cfg: Config | None = None, on_event: OnEvent | None = None) -> ParsedDocument:
    """on_event(event, payload) is called live: "escalation" after each VLM attempt, "warning" once parsing ends."""
    return run(data, filename, cfg or Config.load(), on_event)
