from pathlib import Path

from .env import env

IDENTITY = ("MLPZ", "PESEL")


def load() -> dict:
    e = env()
    prefill = e.get("GENERATOR_PREFILL_IDENTITY", "MLPZ").strip().upper()
    if prefill not in IDENTITY:
        raise ValueError(f"GENERATOR_PREFILL_IDENTITY must be one of {IDENTITY}, got {prefill!r}")
    return {
        "prefill_identity": prefill,  # "Twoje dane" source: MLPZ, or PESEL (+ a PESEL field); address and contact stay MLPZ (Q24)
        "entity_required": e.get("GENERATOR_ENTITY_REQUIRED", "1") not in ("0", "false", "no"),  # S4 checkbox, e.g. "Klub sportowy" (Q31)
        "entity_option": "Osoby prawnej lub jednostki organizacyjnej",  # used when the paper names no entity option
        "templates": Path(__file__).resolve().parent.parent / "generator" / "templates",  # dane/kontakt/finish/presets
    }
