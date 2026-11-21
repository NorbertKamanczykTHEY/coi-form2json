"""Scores a matcher on a cases file: field -> result -> expected.
    cd app/backend && uv run python ../spikes/dictionary-matching/evaluate.py CASES.json [--all] [--db DIR]
accept: dictionary ids, null (no dictionary) or "NEW" (any proposal built from the field's own options)."""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import coi.dictionaries.models  # noqa: E402,F401
from coi.dictionaries import store as ds  # noqa: E402
from coi.dictionaries.matcher import match  # noqa: E402
from coi.store import Store  # noqa: E402


def outcome(m, catalog_ids):
    if m is None:
        return None
    return m.dictionaryName if m.dictionaryName in catalog_ids else "NEW"


def session(db_dir=None):
    st = Store(f"sqlite:///{Path(db_dir or tempfile.mkdtemp())}/eval.sqlite")
    st.init()
    ds.seed(st)
    return st.session()


def score(cases, answer) -> tuple[int, list[str]]:
    """answer(case) -> dictionary id | None | 'NEW'. Returns (#ok, lines)."""
    ok, lines = 0, []
    for c in cases:
        t = time.perf_counter()
        got = answer(c)
        ms = (time.perf_counter() - t) * 1000
        good = got in c["accept"]
        ok += good
        lines.append(f"{'OK' if good else 'XX'} {c['label'][:42]:42} -> {str(got):27} exp {c['accept']}  {ms:.0f}ms")
    return ok, lines


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cases")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--db")
    a = ap.parse_args()
    cases = json.loads(Path(a.cases).read_text())["cases"]
    ids = {d["id"] for d in ds.CATALOG}
    with session(a.db) as s:
        ok, lines = score(cases, lambda c: outcome(match(s, c["label"], "", c["type"], c.get("options", [])), ids))
    print("\n".join(x for x in lines if a.all or x.startswith("XX")))
    print(f"rapidfuzz matcher: {ok}/{len(cases)}")
