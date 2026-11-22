from .env import env


def load() -> dict:
    e = env()
    return {
        # Q1: rungs tried in order; each rung gets one repair round with the gate's objections before the next
        "ladder": [m.strip() for m in e.get("EXTRACTION_LADDER", "mistral/mistral-small-2603,mistral/mistral-large-2512").split(",") if m.strip()],
        "max_tokens": int(e.get("EXTRACTION_MAX_TOKENS", "24000")),  # #9 was cut off at 12k (design §5)
        # Q2: two-stage (skeleton, then fields per page) above this many blocks or with more than one "Wniosek o…"
        "two_stage_blocks": int(e.get("EXTRACTION_TWO_STAGE_BLOCKS", "150")),
        "workers": int(e.get("EXTRACTION_WORKERS", "6")),  # concurrent per-section calls in stage two (per rung)
        # two-stage only: first passes of all rungs start together (wall time ~ the slowest rung, not the sum); costs the
        # stronger rung's first pass also when the weaker one passes
        "parallel_rungs": e.get("EXTRACTION_PARALLEL_RUNGS", "1") not in ("0", "false", "no"),
        "repair_budget_s": float(e.get("EXTRACTION_REPAIR_BUDGET_S", "20")),  # no repair starts after this many seconds: a long tree's repair takes 60-75 s (#8, #9), a short form's a few
    }
