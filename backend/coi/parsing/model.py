"""ParsedDocument contract (docs/superpowers/specs/2026-11-21-parser-contract-design.md)."""
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Literal


class Kind(StrEnum):
    DOCX = "docx"
    DOC = "doc"
    ODS = "ods"
    XLSX = "xlsx"
    PDF_TEXT = "pdf_text"
    PDF_SCAN = "pdf_scan"
    IMAGE = "image"


BlockKind = Literal["heading", "paragraph", "list_item", "table", "footnote"]


@dataclass
class Block:
    kind: BlockKind
    text: str
    level: int | None = None
    rows: list[list[str]] | None = None
    bbox: list[float] | None = None
    confidence: float | None = None


@dataclass
class Page:
    number: int
    blocks: list[Block] = field(default_factory=list)


@dataclass
class ParsedDocument:
    source: dict  # filename, kind, mime, parser, parser_version, seconds
    pages: list[Page]
    warnings: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)  # per-page path: tier, model, gate signals, decision, cost

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def text(self) -> str:
        return "\n".join(b.text for p in self.pages for b in p.blocks)
