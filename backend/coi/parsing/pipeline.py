"""Kind -> parser path, gate, VLM escalation. Every decision lands in trace[], every fallback in warnings[].

doc/docx: Kreuzberg text (+ Word footnotes). No page images without LibreOffice (MPL), so a failed gate is only a warning.
ods/xlsx: own XML reader (borders -> ___ and ☐); if the document gate still fails, our own grid render -> scan route.
pdf: per page. Text layer -> Kreuzberg; no text layer or garbage text (G1/G2) -> scan route.
scan route (image pages, scanned pdf pages): T0 Tesseract pol -> gate -> VLM tiers from ladder.json, each checked against Tesseract as witness.
"""
import json
import tempfile
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

from kreuzberg import render_pdf_page
from PIL import Image

from .. import llm
from ..config import Config
from . import gate
from .detect import ParserEnvironmentError, detect
from .markdown import to_blocks
from .model import Block, Kind, Page, ParsedDocument
from .normalize import normalize
from .parsers import kreuzberg as kz
from .parsers import sheet
from .parsers import tesseract
from .parsers import vision

OnEvent = Callable[[str, dict], None]  # (event, payload), same shape as coi.pipeline.OnEvent


def _render(data: bytes, numbers: list[int], dpi: int = 200) -> dict[int, Image.Image]:
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "in.pdf"
        pdf.write_bytes(data)
        return {n: Image.open(BytesIO(render_pdf_page(str(pdf), n - 1, dpi=dpi))).convert("RGB") for n in numbers}


def _scan_page(n: int, img: Image.Image, ladder: dict, provider: llm.Provider, emit: OnEvent, tessdata: str) -> tuple[list[Block], list[dict], list[str]]:
    t = time.perf_counter()
    witness, conf = tesseract.ocr(vision.png(img), tessdata=tessdata)
    g = gate.text(witness, ladder["gate"], conf)
    trace = [{"page": n, "step": "T0", "parser": "tesseract", "seconds": round(time.perf_counter() - t, 2), "gate": g}]
    if g["ok"]:
        trace[0]["accepted"] = True
        return to_blocks(witness), trace, []
    best = None
    for i, model in enumerate(ladder["tiers"], 1):
        r = vision.transcribe(provider, model, img, ladder)
        m = gate.vlm(r["md"], r["finish"], witness, ladder["gate"])
        if r["error"]:
            m = {"ok": False, "fails": ["error"], "signals": m["signals"]}
        trace.append({"page": n, "step": f"VLM{i}", "parser": "vlm", "model": model, "seconds": round(r["seconds"], 2),
                      "cost": r["cost"], "tiles": r["tiles"], "error": r["error"], "gate": m})
        emit("escalation", {"page": n, "step": f"VLM{i}", "model": model, "accepted": m["ok"], "error": r["error"], "fails": m["fails"]})
        if m["ok"]:
            trace[-1]["accepted"] = True
            return to_blocks(r["md"]), trace, []
        if not r["error"] and r["md"] and (best is None or m["signals"]["witness_coverage"] > best[0]["gate"]["signals"]["witness_coverage"]):
            best = (trace[-1], r["md"])
    # a VLM answer that lost most of the witness text is worse than the OCR itself
    if best and best[0]["gate"]["signals"]["witness_coverage"] >= ladder["gate"].get("min_keep_coverage", 0.5):
        best[0]["accepted"] = True
        return to_blocks(best[1]), trace, [f"page {n}: no VLM tier passed the gate; kept {best[0]['model']}, needs review"]
    trace[0]["accepted"] = True
    return to_blocks(witness), trace, [f"page {n}: all VLM tiers failed; kept Tesseract text, needs review"]


def run(data: bytes, filename: str, cfg: Config, on_event: OnEvent | None = None) -> ParsedDocument:
    t0 = time.perf_counter()
    lock = threading.Lock()

    def emit(event: str, payload: dict):  # pages run in threads; callers get one event at a time
        if on_event:
            with lock:
                on_event(event, payload)

    ladder = json.loads(cfg.ladder_path.read_text())
    kind, mime = detect(data, filename, cfg.max_file_mb, ladder["pdf_min_chars"])
    pages: dict[int, list[Block]] = {}
    scans: dict[int, Image.Image | None] = {}
    warnings: list[str] = []
    trace: list[dict] = []

    if kind == Kind.IMAGE:
        scans = dict(enumerate(vision.split_pages(Image.open(BytesIO(data))), 1))
    else:
        is_pdf = kind in (Kind.PDF_TEXT, Kind.PDF_SCAN)
        is_sheet = kind in (Kind.ODS, Kind.XLSX)
        sheets = sheet.read(data, str(kind)) if is_sheet else []
        texts = [normalize(sheet.to_text(sh)) for sh in sheets] if is_sheet else kz.native(data, mime)
        parser = "sheet-xml" if is_sheet else "kreuzberg"
        for n, text in enumerate(texts, 1):
            if is_pdf and len(text.strip()) < ladder["pdf_min_chars"]:
                trace.append({"page": n, "step": "route", "decision": "no text layer -> scan route"})
                scans[n] = None
                continue
            # G3/G5 are judged on the whole document below: a page of legal clauses has no fields, a footnote may sit on the next page
            g = gate.text(text, ladder["gate"], form_checks=False)
            trace.append({"page": n, "step": "T0", "parser": parser, "gate": g, "accepted": g["ok"] or not is_pdf})
            if g["ok"] or not is_pdf:
                pages[n] = to_blocks(text)
                if not g["ok"]:
                    warnings.append(f"page {n}: gate {g['fails']}, no VLM path for {kind}")
            else:
                scans[n] = None
        if texts and not scans:
            whole = gate.text("\n".join(texts), ladder["gate"])
            trace.append({"page": 0, "step": "T0 document", "parser": parser, "gate": whole})
            if is_sheet and not whole["ok"]:
                try:
                    images = [img for sh in sheets for img in vision.split_pages(sheet.render(sh, font_path=cfg.render_font))]
                except FileNotFoundError as e:
                    raise ParserEnvironmentError(str(e)) from e
                trace.append({"page": 0, "step": "route", "decision": f"gate {whole['fails']} -> own sheet render -> scan route"})
                for e in trace:
                    e["accepted"] = False
                pages, scans = {}, dict(enumerate(images, 1))
                warnings.clear()  # they were about the discarded text pages
            else:
                if "G3 no form fields" in whole["fails"]:
                    warnings.append(f"G3: only {whole['signals']['marks']} form marks found; fields may sit in shapes/text boxes Kreuzberg does not read")
                if "G5 * without footnote" in whole["fails"]:
                    warnings.append("G5: text has * marks but no footnote explaining them; check the source (footnote lost?)")
        if scans and is_pdf:
            scans = _render(data, list(scans))

    if scans:
        try:
            provider = llm.provider(cfg)
        except llm.LLMConfigError as e:
            raise ParserEnvironmentError(str(e)) from e
        with ThreadPoolExecutor(ladder["page_workers"]) as ex:
            for n, (blocks, tr, w) in zip(scans, ex.map(lambda kv: _scan_page(*kv, ladder, provider, emit, cfg.tessdata), scans.items())):
                pages[n] = blocks
                trace += tr
                warnings += w

    for w in warnings:
        emit("warning", {"message": w})

    out = [Page(n, pages[n]) for n in sorted(pages)]
    if not any(p.blocks for p in out):
        warnings.append("empty document")
    used = sorted({e.get("model") or e["parser"] for e in trace if e.get("accepted")})
    source = {"filename": filename, "kind": str(kind), "mime": mime, "parser": " + ".join(used), "parser_version": f"kreuzberg {kz.VERSION}",
              "seconds": round(time.perf_counter() - t0, 2), "cost": round(sum(e.get("cost", 0) for e in trace), 6)}
    return ParsedDocument(source, out, warnings, sorted(trace, key=lambda e: e["page"]))
