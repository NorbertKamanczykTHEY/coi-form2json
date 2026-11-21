"""T0 for page images: Tesseract `pol` CLI (Apache-2.0). Also the independent witness for the VLM gate.

Not through Kreuzberg: its Linux wheels ship without the Tesseract backend (only paddle-ocr and vlm).
"""
import csv
import subprocess
import tempfile
from pathlib import Path

from ..detect import ParserEnvironmentError
from ..normalize import normalize

NAME = "tesseract"


def ocr(png: bytes, lang: str = "pol", timeout: int = 120) -> tuple[str, float | None]:
    """-> (normalized text, mean word confidence 0..1)."""
    with tempfile.TemporaryDirectory() as d:
        src, out = Path(d) / "page.png", Path(d) / "out"
        src.write_bytes(png)
        try:
            subprocess.run(["tesseract", str(src), str(out), "-l", lang, "-c", "tessedit_create_txt=1", "-c", "tessedit_create_tsv=1"],
                           check=True, capture_output=True, timeout=timeout)
        except FileNotFoundError as e:
            raise ParserEnvironmentError("tesseract binary not found (apt install tesseract-ocr tesseract-ocr-pol)") from e
        except subprocess.CalledProcessError as e:  # input is our own PNG, so a failure is the install (e.g. no pol data)
            raise ParserEnvironmentError(f"tesseract failed: {e.stderr.decode(errors='replace')[-300:]}") from e
        text = out.with_suffix(".txt").read_text(encoding="utf-8")
        with out.with_suffix(".tsv").open(encoding="utf-8", newline="") as f:
            conf = [float(r["conf"]) for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE) if r["text"].strip() and float(r["conf"]) >= 0]
    return normalize(text, ocr=True), (sum(conf) / len(conf) / 100 if conf else None)
