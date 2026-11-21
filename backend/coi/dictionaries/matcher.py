"""Field -> dictionary: existing one, a new-dictionary proposal, or None. Rules and the method comparison: app/docs/dictionaries.md.

1. Label vs aliases of every dictionary in the database (rapidfuzz), and the field's options vs dictionary items (coverage).
2. Best score >= DICT_MATCH_THRESHOLD wins. materials/user dictionary -> existing; catalog dictionary -> proposal with its items.
3. Nothing matched, but the field has its own option list that looks like a reusable list of names -> proposal built from the options.
   No option list -> None: a new dictionary is never proposed without items.
"""
import re
from dataclasses import asdict, dataclass

from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import config
from .models import Dictionary, Item, norm

SELECT_ONLY = {"Kraje", "TERYT_4G_DOWODOWY", "WOJEWODZTWO", "POWIAT", "GMINA", "MIEJSCOWOSC", "NUMERY_KIERUNKOWE"}
OTHER = re.compile(r"^(inn[aey]|inne\b|other)", re.I)  # "Inna dyscyplina ___" is a free-text escape, not an item
DECISION = re.compile(r"^(tak|nie|brak|zaliczyc|zwrocic|wniosek|prosze|wyrazam|oswiadczam)\b")


@dataclass
class DictMatch:
    dictionaryName: str
    decision: str  # existing | new
    score: float
    reason: str
    component: str  # SELECT | RADIO | CHECKBOX
    multiLevelTree: bool
    searchEnabled: bool
    proposal: dict | None  # None = the dictionary exists; otherwise goes to report.proposed_dictionaries

    def to_dict(self) -> dict:
        return asdict(self)


def canonical(name: str) -> str:
    """dictionaryName after the alias map in coi/config/dictionaries.py (TERYT_DOWODOWY -> TERYT_4G_DOWODOWY)."""
    return config("dictionaries.aliases").get(name, name)


def _label(s: str) -> str:
    return norm(re.sub(r"\(.*?\)|[_.…]{2,}", " ", s))  # "(opcjonalnie)", "......" are not part of the meaning


def label_score(label: str, alias: str) -> float:
    """1.0 exact; fuzzy ratio for OCR typos; an alias contained as whole words in a longer label scores by how much it covers."""
    a, b = _label(label), norm(alias)
    if not a or not b:
        return 0.0
    score = fuzz.ratio(a, b) / 100
    if re.search(rf"\b{re.escape(b)}\b", a) and (cover := len(b) / len(a)) >= 0.5:
        score = max(score, 0.75 + 0.25 * cover)
    return score


def _options(options) -> list[str]:
    return [o for o in (str(x).strip() for x in options or ()) if o and not OTHER.match(o)]


def coverage(s: Session, options: list[str]) -> dict[str, float]:
    """Share of the field's options that are item names of each dictionary (exact after norm)."""
    keys = {norm(o) for o in options}
    if len(keys) < 2:
        return {}
    hits = s.execute(select(Item.dictionary_id, func.count(func.distinct(Item.norm))).where(Item.norm.in_(keys)).group_by(Item.dictionary_id))
    return {did: n / len(keys) for did, n in hits if n >= 2}


def _shape(d: Dictionary | None, type_: str, n_items: int, levels: list) -> tuple[str, bool, bool]:
    if d is not None and d.id in SELECT_ONLY or type_ not in ("RADIO", "CHECKBOX"):
        comp = "SELECT"
    elif type_ == "RADIO" and n_items > 5:
        comp = "SELECT"
    else:
        comp = type_
    return comp, len(levels) > 1, n_items > 15


def _tree(s: Session, did: str) -> list[dict]:
    rows = s.execute(select(Item.id, Item.name, Item.parent, Item.value).where(Item.dictionary_id == did).order_by(Item.pos)).all()
    nodes = {r.id: {"id": r.id, "name": r.name} | ({"value": r.value} if r.value else {}) for r in rows}
    roots = []
    for r in rows:
        (nodes[r.parent].setdefault("children", []) if r.parent in nodes else roots).append(nodes[r.id])
    return roots


def looks_like_dictionary(label: str, options: list[str]) -> bool:
    """Stage 3 (K1-K3 from the flow review, as a rule): many short noun-like options, not decisions or sentences."""
    if len(options) < 8:
        return False
    short = sum(len(o.split()) <= 4 for o in options) / len(options)
    return short >= 0.9 and not any(DECISION.match(norm(o)) for o in options)


def _proposal_id(label: str) -> str:
    return re.sub(r"_+", "_", norm(label).upper().replace(" ", "_"))[:64].strip("_") or "NOWY_SLOWNIK"


def match(s: Session, label: str, source_label: str = "", type: str = "", options=()) -> DictMatch | None:
    opts = _options(options)
    cov = coverage(s, opts)
    best: tuple[float, Dictionary, str] | None = None
    for d in s.scalars(select(Dictionary)):
        lab = max((label_score(x, a), a) for x in (label, source_label) if x for a in [d.name, *d.aliases]) if (label or source_label) else (0.0, "")
        cand = max((lab[0], f"etykieta ~ alias '{lab[1]}' ({lab[0]:.2f})"), (cov.get(d.id, 0.0), f"opcje w słowniku: {cov.get(d.id, 0):.0%}"))
        if best is None or cand[0] > best[0]:
            best = (cand[0], d, cand[1])
    if best and best[0] >= config("dictionaries.match_threshold"):
        score, d, why = best
        n = s.scalar(select(func.count()).select_from(Item).where(Item.dictionary_id == d.id)) or 0
        comp, tree, search = _shape(d, type, n, d.levels)
        if d.origin == "catalog":
            prop = {"id": d.id, "name": d.name, "description": d.description, "levels": d.levels, "items": _tree(s, d.id), "source": "catalog"}
            return DictMatch(d.id, "new", round(score, 3), f"{why}; słownik z naszego katalogu, nie ma go w materiałach", comp, tree, search, prop)
        return DictMatch(d.id, "existing", round(score, 3), why, comp, tree, search, None)
    if opts and looks_like_dictionary(label, opts):
        did = _proposal_id(label or source_label)
        comp, tree, search = _shape(None, type, len(opts), ["pozycja"])
        prop = {"id": did, "name": label or source_label, "description": "", "levels": ["pozycja"], "items": [{"name": o} for o in opts], "source": "document"}
        return DictMatch(did, "new", 0.0, f"brak pasującego słownika; {len(opts)} krótkich nazw w opcjach pola", comp, tree, search, prop)
    return None
