from .env import env


def load() -> dict:
    e = env()
    return {
        # Q1: rungs tried in order; each rung gets one repair round with the gate's objections before the next
        "ladder": [m.strip() for m in e.get("EXTRACTION_LADDER", "mistral/mistral-small-2603,mistral/mistral-large-2512").split(",") if m.strip()],
        "max_tokens": int(e.get("EXTRACTION_MAX_TOKENS", "24000")),  # #9 was cut off at 12k (design §5)
        # Q2: two-stage (skeleton, then fields per page) above this many blocks or with more than one "Wniosek o…"
        "two_stage_blocks": int(e.get("EXTRACTION_TWO_STAGE_BLOCKS", "150")),
        "workers": int(e.get("EXTRACTION_WORKERS", "4")),  # parallel per-page calls in stage two
    }
