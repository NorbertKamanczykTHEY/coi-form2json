"""Anchors p<page>.b<index>: ParsedDocument -> {anchor: text} and the anchored text the LLM cites from."""
import re

from coi.parsing.model import ParsedDocument

RANGE = re.compile(r"(p\d+\.b\d+)-(p\d+\.b\d+)")


def blocks_of(doc: ParsedDocument) -> dict[str, str]:
    """Insertion order = reading order; expand() relies on it for ranges."""
    return {f"p{p.number}.b{i}": b.text for p in doc.pages for i, b in enumerate(p.blocks)}


def anchored(doc: ParsedDocument, only: set[str] | None = None) -> str:
    out = []
    for p in doc.pages:
        for i, b in enumerate(p.blocks):
            tag = f"p{p.number}.b{i}"
            if only is not None and tag not in only:
                continue
            if b.kind == "heading":
                out.append(f"[{tag}] {'#' * (b.level or 1)} {b.text}")
            elif b.kind == "table" and b.rows:
                out.append(f"[{tag}] TABLE")
                out += ["  | " + " | ".join(r) + " |" for r in b.rows]
            else:
                out.append(f"[{tag}] {b.text}")
    return "\n".join(out)


def expand(anchors: list[str], blocks: dict[str, str]) -> list[str]:
    """'p1.b3-p2.b4' -> every anchor between them in reading order (cross-page too); unknown anchors pass through."""
    order = list(blocks)
    out = []
    for a in anchors:
        a = a.strip().strip("[]")
        m = RANGE.fullmatch(a)
        if m and m[1] in blocks and m[2] in blocks:
            i, j = order.index(m[1]), order.index(m[2])
            out += order[min(i, j):max(i, j) + 1]
        else:
            out.append(a)
    return out


def src_text(anchors: list[str], blocks: dict[str, str]) -> str:
    return " ".join(blocks.get(a, "") for a in expand(anchors, blocks))
