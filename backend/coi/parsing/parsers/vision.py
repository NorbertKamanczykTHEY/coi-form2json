"""Page image -> VLM through the provider adapter (coi.llm) -> markdown transcription. Retries as horizontal tiles when cut at max_tokens."""
import base64
import io

from PIL import Image

from ... import llm
from ...prompts import prompt
from ..normalize import normalize

A4 = 1.4142


def split_pages(img: Image.Image) -> list[Image.Image]:
    """A tall image is several A4 pages stitched together (renders in materials/): cut at page height."""
    img = img.convert("RGB")
    page_h = round(img.width * A4)
    if img.height < page_h * 1.3:
        return [img]
    return [img.crop((0, y, img.width, min(y + page_h, img.height))) for y in range(0, img.height, page_h) if img.height - y > 50]


def png(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def _data_url(img: Image.Image, width: int) -> str:
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.Resampling.LANCZOS)
    b = io.BytesIO()
    img.save(b, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def _ask(llm_: llm.Provider, model: str, img: Image.Image, ladder: dict) -> llm.Reply:
    content = [{"type": "image_url", "image_url": {"url": _data_url(img, ladder["page_width"])}}, {"type": "text", "text": prompt("vision_page")}]
    return llm_.chat(model, content, ladder["max_tokens"])


def _tiles(img: Image.Image, n: int) -> list[Image.Image]:
    h, pad = img.height / n, round(img.height * 0.02)  # overlap so no text line is cut in half (may repeat one line)
    return [img.crop((0, max(0, round(i * h) - pad), img.width, min(img.height, round((i + 1) * h) + pad))) for i in range(n)]


def transcribe(llm_: llm.Provider, model: str, img: Image.Image, ladder: dict) -> dict:
    """-> {md, finish, cost, seconds, tiles, error}"""
    out = {"md": "", "finish": None, "cost": 0.0, "seconds": 0.0, "tiles": 1, "error": None}
    try:
        r = _ask(llm_, model, img, ladder)
        out.update(md=r.text, finish=r.finish, cost=r.cost, seconds=r.seconds)
        if r.finish == "length":  # gate M1: retry on smaller pieces
            parts = [_ask(llm_, model, t, ladder) for t in _tiles(img, ladder["tile_rows"])]
            out.update(md="\n\n".join(p.text for p in parts), tiles=len(parts),
                       finish="length" if any(p.finish == "length" for p in parts) else "stop",
                       cost=out["cost"] + sum(p.cost for p in parts), seconds=out["seconds"] + sum(p.seconds for p in parts))
    except Exception as e:  # noqa: BLE001 - a failed call is a failed tier; the ladder escalates
        out["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    out["md"] = normalize(out["md"].strip().removeprefix("```markdown").removeprefix("```").removesuffix("```"))
    return out
