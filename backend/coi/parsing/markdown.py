"""Markdown <-> blocks. Every parser emits markdown-ish text; to_blocks() turns it into the contract, to_markdown() back for the LLM."""
import re

from .model import Block, ParsedDocument

HEAD_MD = re.compile(r"^(#{1,6})\s+(.*)")
HEAD_L2 = re.compile(r"^(?:[A-Z]|\d+)\.\d+\.?\s+\S")  # B.1, 2.1
HEAD_L1 = re.compile(r"^(?:[A-Z]|[IVX]+)\.\s+\S")  # A., I.  ("1." is too often a list item in forms)
LIST = re.compile(r"^(?:[-*•]\s+|\d+[.)]\s+|[a-z]\)\s+|☐)")
FOOT = re.compile(r"^\*{1,3}\)?\s*[^*\s](?:.*[^*])?$")  # "* niepotrzebne skreślić", "**) ..."; not "**bold**"
TABLE_SEP = re.compile(r"^\|?[\s:|-]+\|[\s:|-]*$")


def _is_caps_heading(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    return 3 <= len(letters) and len(s) <= 120 and all(c.isupper() for c in letters)


def _row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    out = []
    for c in cells:  # merged cells repeat their text in every spanned column
        if not out or c != out[-1] or not c:
            out.append(c)
    return out


def _line(line: str) -> Block:
    line = re.sub(r"^\*\*(.+)\*\*$", r"\1", line)  # whole-line bold (VLM); inner ** are footnote marks
    if m := HEAD_MD.match(line):
        text = m[2].strip("* ")
        return Block("heading", text, level=2 if HEAD_L2.match(text) else 1 if HEAD_L1.match(text) else min(len(m[1]), 2))
    if HEAD_L2.match(line) and len(line) <= 120:
        return Block("heading", line, level=2)
    if (HEAD_L1.match(line) and len(line) <= 120) or _is_caps_heading(line):
        return Block("heading", line, level=1)
    if FOOT.match(line):
        return Block("footnote", line)
    if LIST.match(line):
        return Block("list_item", line)
    return Block("paragraph", line)


def _table(rows: list[list[str]]) -> list[Block]:
    """Spreadsheets and layout tables: drop empty rows/columns, a row with one filled cell is a plain line."""
    out: list[Block] = []
    run: list[list[str]] = []

    def emit():
        if run:
            keep = [j for j in range(max(map(len, run))) if any(j < len(r) and r[j] for r in run)]
            t = [[r[j] if j < len(r) else "" for j in keep] for r in run]
            out.append(Block("table", "\n".join(" | ".join(c for c in r if c) for r in t), rows=t))
            run.clear()

    for r in rows:
        cells = [c for c in r if c]
        if len(cells) == 1:
            emit()
            out.append(_line(cells[0]))
        elif cells:
            run.append(r)
    emit()
    return out


def to_blocks(md: str) -> list[Block]:
    blocks: list[Block] = []
    table: list[list[str]] = []
    for raw in md.splitlines() + [""]:
        line = raw.strip()
        if line.startswith("|"):
            if not TABLE_SEP.match(line):
                table.append(_row(line))
            continue
        if table:
            blocks += _table(table)
            table = []
        if line and line not in ("---", "***"):
            blocks.append(_line(line))
    return blocks


def to_markdown(doc: ParsedDocument) -> str:
    out = []
    for p in doc.pages:
        if len(doc.pages) > 1:
            out.append(f"<!-- strona {p.number} -->")
        for b in p.blocks:
            if b.kind == "heading":
                out.append("#" * (b.level or 1) + " " + b.text)
            elif b.kind == "table" and b.rows:
                w = max(len(r) for r in b.rows)
                rows = [r + [""] * (w - len(r)) for r in b.rows]
                out += ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w] + ["| " + " | ".join(r) + " |" for r in rows[1:]]
            elif b.kind == "list_item" and not LIST.match(b.text):
                out.append("- " + b.text)
            else:
                out.append(b.text)
            out.append("")
    return "\n".join(out).strip() + "\n"
