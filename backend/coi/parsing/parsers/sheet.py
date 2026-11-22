"""ODS / XLSX read from the XML inside (stdlib only), with the layout signals Kreuzberg drops.

Spreadsheet forms draw places to fill in with cell borders, not with dots or glyphs:
- a run of >= MIN_LINE empty cells with a bottom border, not part of a frame (no left/right edge in the run) -> ___
- an empty single cell boxed on all four sides -> ☐
Text cells are grouped into visual lines by their row span; markers join the line on their row (or within
NEAR rows) and everything is ordered by column. Each visible sheet is one page. Geometry is kept for render().
ElementTree never resolves external entities; Python's bundled expat guards against entity expansion.
"""
import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from xml.etree import ElementTree as ET

MIN_LINE = 3  # columns
NEAR = 2  # rows a marker may sit above/below its label line
MAX_ROWS, MAX_COLS = 5000, 512  # repeated rows/columns run to 1M in files from Calc

O = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
}
X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _o(prefix: str, name: str) -> str:
    return f"{{{O[prefix]}}}{name}"


@dataclass
class Cell:
    r0: int
    c0: int
    r1: int
    c1: int
    text: str
    edges: str  # subset of "lrtb"


@dataclass
class Sheet:
    name: str
    cells: list[Cell] = field(default_factory=list)
    col_w: dict[int, float] = field(default_factory=dict)  # points
    row_h: dict[int, float] = field(default_factory=dict)  # points


def _length_pt(v: str | None) -> float | None:
    m = re.match(r"([\d.]+)(cm|mm|in|pt)", v or "")
    return float(m[1]) * {"cm": 28.35, "mm": 2.835, "in": 72, "pt": 1}[m[2]] if m else None


# ---------- ODS ----------

def _ods_text(el) -> str:
    out = []

    def walk(e):
        tag = e.tag.split("}")[1]
        if tag == "annotation":  # comments: kept, in brackets
            out.append(" [" + " ".join("".join(p.itertext()) for p in e.iter(_o("text", "p"))) + "] ")
            return
        if tag == "s":
            out.append(" " * int(e.get(_o("text", "c"), "1")))
        elif tag in ("tab", "line-break"):
            out.append(" ")
        out.append(e.text or "")
        for ch in e:
            walk(ch)
            out.append(ch.tail or "")
        if tag in ("p", "h"):
            out.append("\n")

    for ch in el:
        walk(ch)
    return " ".join("".join(out).split())


def _ods_styles(*roots) -> dict[str, dict]:
    styles = {}
    for root in roots:
        for st in root.iter(_o("style", "style")):
            props = {}
            for p in st:
                props |= {k.split("}")[1]: v for k, v in p.attrib.items()}
            styles[st.get(_o("style", "name"))] = {"parent": st.get(_o("style", "parent-style-name")), **props}

    def edges(name: str | None) -> str:
        p, seen = {}, set()
        while name in styles and name not in seen:  # child overrides parent
            seen.add(name)
            p = styles[name] | p
            name = styles[name]["parent"]
        on = lambda v: v is not None and v != "none" and not re.match(r"0+(\.0+)?[a-z]*(\s|$)", v)  # "0pt solid" = no line; "0.06pt" is one  # noqa: E731
        if on(p.get("border")):
            return "lrtb"
        return "".join(s for s, k in zip("lrtb", ("border-left", "border-right", "border-top", "border-bottom")) if on(p.get(k)))

    return {"edges": edges, "raw": styles}


def _ods(data: bytes) -> list[Sheet]:
    with zipfile.ZipFile(BytesIO(data)) as z:
        content = ET.fromstring(z.read("content.xml"))
        common = ET.fromstring(z.read("styles.xml")) if "styles.xml" in z.namelist() else content
    st = _ods_styles(common, content)
    sheets = []
    for table in content.iter(_o("table", "table")):
        if st["raw"].get(table.get(_o("table", "style-name")), {}).get("display") == "false":
            continue
        sh = Sheet(table.get(_o("table", "name"), ""))
        col_default, c = [], 0
        for col in table.iter(_o("table", "table-column")):
            n = min(int(col.get(_o("table", "number-columns-repeated"), "1")), MAX_COLS)
            w = _length_pt(st["raw"].get(col.get(_o("table", "style-name")), {}).get("column-width"))
            for i in range(c, c + n):
                col_default.append(col.get(_o("table", "default-cell-style-name")))
                if w:
                    sh.col_w[i] = w
            c += n
        r = 0
        for row in table.iter(_o("table", "table-row")):
            rep = int(row.get(_o("table", "number-rows-repeated"), "1"))
            h = _length_pt(st["raw"].get(row.get(_o("table", "style-name")), {}).get("row-height"))
            c = 0
            for cell in row:
                n = int(cell.get(_o("table", "number-columns-repeated"), "1"))
                if cell.tag != _o("table", "table-cell") or c >= MAX_COLS:
                    c += n  # covered cells belong to the span of the cell that covers them
                    continue
                style = cell.get(_o("table", "style-name")) or (col_default[c] if c < len(col_default) else None)
                text, edges = _ods_text(cell), st["edges"](style)
                cs = int(cell.get(_o("table", "number-columns-spanned"), "1"))
                rs = int(cell.get(_o("table", "number-rows-spanned"), "1"))
                if text or edges:
                    for dr in range(min(rep, MAX_ROWS - r) if not text else 1):
                        for i in range(min(n, MAX_COLS - c)):
                            sh.cells.append(Cell(r + dr, c + i, r + dr + rs - 1, c + i + cs - 1, text, edges))
                c += n
            for dr in range(min(rep, MAX_ROWS - r) if h else 0):
                sh.row_h[r + dr] = h
            r += rep
            if r >= MAX_ROWS:
                break
        sheets.append(sh)
    return sheets


# ---------- XLSX ----------

def _ref(ref: str) -> tuple[int, int]:
    m = re.match(r"([A-Z]+)(\d+)", ref)
    c = 0
    for ch in m[1]:
        c = c * 26 + ord(ch) - 64
    return int(m[2]) - 1, c - 1


def _xlsx(data: bytes) -> list[Sheet]:
    with zipfile.ZipFile(BytesIO(data)) as z:
        names = set(z.namelist())
        read = lambda p: ET.fromstring(z.read(p)) if p in names else None  # noqa: E731
        shared = [("".join(t.text or "" for t in si.iter(X + "t"))) for si in (read("xl/sharedStrings.xml") or [])]
        styles = read("xl/styles.xml")
        borders, xfs = [], []
        if styles is not None:
            for b in styles.iter(X + "border"):
                borders.append("".join(s for s, k in zip("lrtb", ("left", "right", "top", "bottom"))
                                       if (e := b.find(X + k)) is not None and e.get("style") not in (None, "none")))
            cell_xfs = styles.find(X + "cellXfs")
            xfs = [int(x.get("borderId", "0")) for x in (cell_xfs if cell_xfs is not None else [])]
        rels = {r.get("Id"): r.get("Target") for r in (read("xl/_rels/workbook.xml.rels") or [])}
        sheets = []
        for s in read("xl/workbook.xml").iter(X + "sheet"):
            if s.get("state") in ("hidden", "veryHidden"):
                continue
            target = rels.get(s.get(REL), "")
            ws = read("xl/" + target.lstrip("/").removeprefix("xl/"))
            if ws is None:
                continue
            sh = Sheet(s.get("name", ""))
            for col in ws.iter(X + "col"):
                for i in range(int(col.get("min")) - 1, min(int(col.get("max")), MAX_COLS)):
                    sh.col_w[i] = float(col.get("width", "8.43")) * 5.25  # character widths -> points
            merges = {}
            for m in ws.iter(X + "mergeCell"):
                a, b = m.get("ref").split(":")
                merges[_ref(a)] = _ref(b)
            for row in ws.iter(X + "row"):
                if row.get("ht"):
                    sh.row_h[int(row.get("r")) - 1] = float(row.get("ht"))
            for c in ws.iter(X + "c"):
                r0, c0 = _ref(c.get("r"))
                if r0 >= MAX_ROWS or c0 >= MAX_COLS:
                    continue
                t, v = c.get("t"), c.find(X + "v")
                if t == "s" and v is not None:
                    text = shared[int(v.text)]
                elif t == "inlineStr":
                    text = "".join(x.text or "" for x in c.iter(X + "t"))
                else:
                    text = v.text if v is not None and v.text else ""
                xf = int(c.get("s", "0"))
                edges = borders[xfs[xf]] if xf < len(xfs) and xfs[xf] < len(borders) else ""
                r1, c1 = merges.get((r0, c0), (r0, c0)) if text else (r0, c0)  # borders stay per cell
                if text.strip() or edges:
                    sh.cells.append(Cell(r0, c0, r1, c1, " ".join(text.split()), edges))
            sheets.append(sh)
    return sheets


# ---------- layout -> text ----------

def _edges_grid(sh: Sheet) -> dict[tuple[int, int], set[str]]:
    g: dict[tuple[int, int], set[str]] = {}
    for c in sh.cells:
        for r in range(c.r0, c.r1 + 1):
            for col in range(c.c0, c.c1 + 1):
                e = g.setdefault((r, col), set())
                e |= {"l"} & set(c.edges) if col == c.c0 else set()
                e |= {"r"} & set(c.edges) if col == c.c1 else set()
                e |= {"t"} & set(c.edges) if r == c.r0 else set()
                e |= {"b"} & set(c.edges) if r == c.r1 else set()
    return g


def markers(sh: Sheet) -> list[tuple[int, int, str]]:
    """(row, col, '___' | '☐') found from borders."""
    filled = {(r, c) for x in sh.cells if x.text for r in range(x.r0, x.r1 + 1) for c in range(x.c0, x.c1 + 1)}
    grid = _edges_grid(sh)
    boxes = {(x.r0, x.c0) for x in sh.cells if not x.text and x.r0 == x.r1 and x.c0 == x.c1 and set("lrtb") <= set(x.edges)}
    out = [(r, c, "☐") for r, c in boxes]
    rows: dict[int, list[int]] = {}
    for (r, c), e in grid.items():
        if "b" in e and (r, c) not in filled and (r, c) not in boxes:
            rows.setdefault(r, []).append(c)
    for r, cols in rows.items():
        cols.sort()
        run = [cols[0]]
        for c in cols[1:] + [None]:
            if c is not None and c == run[-1] + 1:
                run.append(c)
                continue
            if len(run) >= MIN_LINE and not any(grid[(r, x)] & {"l", "r"} for x in run):  # side edges = a frame, not a line
                out.append((r, run[0], "___"))
            if c is not None:
                run = [c]
    return out


def to_text(sh: Sheet) -> str:
    groups: list[dict] = []
    for c in sorted((c for c in sh.cells if c.text), key=lambda c: (c.r0, c.c0)):
        if groups and c.r0 <= groups[-1]["r1"]:
            groups[-1]["r1"] = max(groups[-1]["r1"], c.r1)
            groups[-1]["items"].append((c.c0, c.text))
        else:
            groups.append({"r0": c.r0, "r1": c.r1, "items": [(c.c0, c.text)]})
    loose: list[dict] = []
    for r, col, mark in sorted(markers(sh)):
        dist = [(0 if g["r0"] <= r <= g["r1"] else min(abs(r - g["r0"]), abs(r - g["r1"])), -g["r0"], i) for i, g in enumerate(groups)]
        d, _, i = min(dist, default=(NEAR + 1, 0, -1))
        target = groups[i] if d <= NEAR else None
        if target is None:  # a line with no label near it: its own line; stacked duplicates collapse
            if loose and loose[-1]["items"] == [(col, mark)] and r - loose[-1]["r1"] <= 4:
                loose[-1]["r1"] = r
                continue
            loose.append({"r0": r, "r1": r, "items": [(col, mark)]})
        elif (col, mark) not in target["items"]:
            target["items"].append((col, mark))
    lines = sorted(groups + loose, key=lambda g: (g["r0"], g["items"][0][0]))
    return "\n".join(" ".join(t for _, t in sorted(g["items"], key=lambda x: x[0])) for g in lines)


def read(data: bytes, kind: str) -> list[Sheet]:
    try:
        return _ods(data) if kind == "ods" else _xlsx(data)
    except (zipfile.BadZipFile, KeyError, ET.ParseError, ValueError, AttributeError, TypeError) as e:
        raise ValueError(f"broken {kind} file: {type(e).__name__}: {e}") from e


# ---------- fallback: own render (no LibreOffice) -> page images for the VLM path ----------

FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
         "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"]


def _font(size: int, path: str = ""):
    from PIL import ImageFont

    for p in [path] * bool(path) + FONTS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    raise FileNotFoundError("no TTF font with Polish glyphs (apt install fonts-dejavu-core or set RENDER_FONT)")


def _wrap(draw, text: str, font, width: float) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        if cur and draw.textlength(cur + " " + w, font=font) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + [cur] * bool(cur)


def render(sh: Sheet, width_px: int = 1654, font_path: str = ""):
    """Grid render: column widths, row heights, cell borders and wrapped text, rows grown to fit their text.
    shortcut: no fonts/colours/alignment from the file; enough for a VLM to see labels next to lines and boxes."""
    from PIL import Image, ImageDraw

    cols = max((c.c1 for c in sh.cells), default=0) + 1
    rows = max((c.r1 for c in sh.cells), default=0) + 1
    known = sorted(sh.col_w.values())
    cw = [sh.col_w.get(c, known[len(known) // 2] if known else 48.0) for c in range(cols)]
    scale = width_px / sum(cw)
    font = _font(max(12, round(9 * scale)), font_path)
    draw = ImageDraw.Draw(Image.new("L", (1, 1)))
    line_h = font.size * 1.25
    rh = [sh.row_h.get(r, 12.8) * scale for r in range(rows)]
    x = [0.0]
    for w in cw:
        x.append(x[-1] + w * scale)
    for c in sorted((c for c in sh.cells if c.text and c.r0 == c.r1), key=lambda c: c.r0):  # grow rows to fit text
        need = len(_wrap(draw, c.text, font, x[c.c1 + 1] - x[c.c0] - 4)) * line_h + 4
        rh[c.r0] = max(rh[c.r0], need)
    y = [0.0]
    for h in rh:
        y.append(y[-1] + h)
    img = Image.new("RGB", (width_px, round(y[-1]) + 20), "white")
    d = ImageDraw.Draw(img)
    for c in sh.cells:
        x0, x1, y0, y1 = x[c.c0], x[c.c1 + 1], y[c.r0], y[c.r1 + 1]
        for side, xy in zip("lrtb", ((x0, y0, x0, y1), (x1, y0, x1, y1), (x0, y0, x1, y0), (x0, y1, x1, y1))):
            if side in c.edges:
                d.line(xy, fill="black", width=2)
        for i, ln in enumerate(_wrap(d, c.text, font, x1 - x0 - 4)):
            d.text((x0 + 2, y0 + 2 + i * line_h), ln, font=font, fill="black")
    return img
