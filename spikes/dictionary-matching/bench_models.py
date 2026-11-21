"""Compares field -> dictionary methods. Thresholds are tuned on the dev set (#1-#9) and reported on the held-out set.
    cd app/backend && uv run --with torch --with transformers --with sentence-transformers --with sentencepiece --with protobuf \
        python ../spikes/dictionary-matching/bench_models.py [--db DIR] [--skip-llm]
Writes results.json next to this file. Eden key comes from app/.env through coi.config; it is never printed."""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))
from evaluate import outcome, session  # noqa: E402

from coi.config import Config  # noqa: E402
from coi.dictionaries import store as ds  # noqa: E402
from coi.dictionaries.matcher import _options, looks_like_dictionary, match  # noqa: E402
from coi.llm import provider  # noqa: E402

CAT = ds.CATALOG
IDS = [d["id"] for d in CAT]
DOCS = [f"{d['name']}. {d['description']} Typowe etykiety: {', '.join(d['aliases'])}." for d in CAT]
DEV = json.loads((HERE.parents[1] / "backend/tests/dictionaries/match_cases.json").read_text())["cases"]
HELD = json.loads((HERE / "heldout_cases.json").read_text())["cases"]


def text(c) -> str:
    o = _options(c.get("options"))
    return c["label"] + (f" (opcje: {', '.join(o[:6])})" if o else "")


def decide(scores: np.ndarray, thr: float, c, is_dict_list) -> str | None:
    i = int(scores.argmax())
    if scores[i] >= thr:
        return IDS[i]
    o = _options(c.get("options"))
    return "NEW" if o and is_dict_list(c, o) else None


def rule(c, o):
    return looks_like_dictionary(c["label"], o)


def acc(cases, answers) -> float:
    return sum(a in c["accept"] for c, a in zip(cases, answers)) / len(cases)


def split(cases, answers) -> dict:
    pos = [(c, a) for c, a in zip(cases, answers) if None not in c["accept"]]
    neg = [(c, a) for c, a in zip(cases, answers) if c["accept"] == [None]]
    return {"should_match": f"{sum(a in c['accept'] for c, a in pos)}/{len(pos)}", "should_not": f"{sum(a is None for c, a in neg)}/{len(neg)}"}


def tune(score_fn, is_dict_list) -> tuple[float, dict]:
    """score_fn(cases) -> matrix [n_cases, n_dicts], computed once per set; threshold from a grid on DEV."""
    t = time.perf_counter()
    dev = score_fn(DEV)
    per_field_ms = (time.perf_counter() - t) / len(DEV) * 1000
    grid = sorted(set(np.round(dev.max(1), 3)))
    best = max(grid, key=lambda th: (acc(DEV, [decide(r, th, c, is_dict_list) for r, c in zip(dev, DEV)]), th))
    held = score_fn(HELD)
    a_dev = [decide(r, best, c, is_dict_list) for r, c in zip(dev, DEV)]
    a_held = [decide(r, best, c, is_dict_list) for r, c in zip(held, HELD)]
    return best, {"threshold": float(best), "dev": acc(DEV, a_dev), "held": acc(HELD, a_held), "held_split": split(HELD, a_held),
                  "ms_per_field": round(per_field_ms, 1), "answers_held": a_held, "answers_dev": a_dev}


def run_rapidfuzz(db):
    out = {}
    with session(db) as s:
        for name, cases in (("dev", DEV), ("held", HELD)):
            t = time.perf_counter()
            a = [outcome(match(s, c["label"], "", c["type"], c.get("options", [])), set(IDS)) for c in cases]
            out[name] = acc(cases, a)
            out[f"answers_{name}"] = a
            out["ms_per_field"] = round((time.perf_counter() - t) / len(cases) * 1000, 1)
        out["held_split"] = split(HELD, out["answers_held"])
    out["threshold"] = 0.8
    return out


def run_embeddings(model_name, query_prefix="", doc_prefix=""):
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(model_name, device="cpu")
    D = m.encode([doc_prefix + d for d in DOCS], normalize_embeddings=True)
    A = [m.encode([doc_prefix + a for a in d["aliases"]], normalize_embeddings=True) for d in CAT]
    m.encode([query_prefix + "rozgrzewka"])

    def score(cases):
        Q = m.encode([query_prefix + text(c) for c in cases], normalize_embeddings=True)
        return np.stack([np.maximum(Q @ D.T, np.stack([(Q @ a.T).max(1) for a in A], 1))])[0]
    return tune(score, rule)[1]


def run_reranker(model_name):
    from sentence_transformers import CrossEncoder
    m = CrossEncoder(model_name, device="cpu", max_length=256)
    m.predict([("x", "y")])

    def score(cases):
        pairs = [(text(c), d) for c in cases for d in DOCS]
        s = np.asarray(m.predict(pairs, batch_size=32))
        s = 1 / (1 + np.exp(-s)) if s.min() < 0 or s.max() > 1 else s
        return s.reshape(len(cases), len(DOCS))
    return tune(score, rule)[1]


def run_nli(model_name):
    from transformers import pipeline
    zs = pipeline("zero-shot-classification", model=model_name, device=-1)
    names = [f"{d['name']} ({d['description'][:80]})" for d in CAT]
    lists = ["lista nazw z oficjalnego rejestru, przepisu lub klasyfikacji", "lista odpowiedzi, decyzji lub oświadczeń tego formularza"]

    def is_dict_list(c, o):
        r = zs("Opcje: " + ", ".join(o[:12]), lists, hypothesis_template="To jest {}.")
        return r["labels"][0] == lists[0]

    def score(cases):
        out = []
        for c in cases:
            r = zs("Pole formularza: " + text(c), names + ["nic z powyższych"], hypothesis_template="Wartość tego pola to {}.", multi_label=False)
            sc = dict(zip(r["labels"], r["scores"]))
            out.append([sc[n] for n in names])
        return np.asarray(out)
    return tune(score, is_dict_list)[1]


def run_eden_embeddings(model):
    cl = provider(Config.load())._client
    cost = [0.0]

    def emb(xs):
        r = cl.embeddings.create(model=model, input=xs)
        cost[0] += float((r.model_extra or {}).get("cost") or 0)
        v = np.asarray([d.embedding for d in r.data])
        return v / np.linalg.norm(v, axis=1, keepdims=True)
    D = emb(DOCS)
    A = [emb(d["aliases"]) for d in CAT]

    def score(cases):
        Q = emb([text(c) for c in cases])
        return np.maximum(Q @ D.T, np.stack([(Q @ a.T).max(1) for a in A], 1))
    r = tune(score, rule)[1]
    r["cost_usd_total"] = cost[0]
    return r


def run_llm(model, db):
    p = provider(Config.load())
    tmpl = (HERE / "llm_decision.md").read_text()
    dicts = "\n".join(f"- {d['id']}: {d['description']}" for d in CAT)
    cost, secs = [0.0], [0.0]

    def ask(c):
        o = _options(c.get("options"))
        r = p.chat(model, tmpl.format(dictionaries=dicts, label=c["label"], type=c["type"], options="; ".join(o) or "brak"), 120)
        cost[0] += r.cost
        secs[0] += r.seconds
        try:
            j = json.loads(re.search(r"\{.*\}", r.text, re.S)[0])
        except (TypeError, ValueError):
            return None
        if j.get("dictionary") in IDS:
            return j["dictionary"]
        return "NEW" if o and j.get("K1") and j.get("K2") and j.get("K3") else None
    out = {}
    for name, cases in (("dev", DEV), ("held", HELD)):
        a = [ask(c) for c in cases]
        out[name], out[f"answers_{name}"] = acc(cases, a), a
    out["held_split"] = split(HELD, out["answers_held"])
    n = len(DEV) + len(HELD)
    out |= {"ms_per_field": round(secs[0] / n * 1000), "cost_usd_per_field": cost[0] / n, "cost_usd_total": cost[0], "threshold": None}
    return out


def run_hybrid(db, model_answers_held, model_answers_dev):
    """rapidfuzz decides when it matches; otherwise the model's answer."""
    out = {}
    with session(db) as s:
        for name, cases, ma in (("dev", DEV, model_answers_dev), ("held", HELD, model_answers_held)):
            a = []
            for c, m_ans in zip(cases, ma):
                m = match(s, c["label"], "", c["type"], c.get("options", []))
                a.append(outcome(m, set(IDS)) if m and m.score > 0 else m_ans)  # score 0 = the stage-3 rule; the model decides those
            out[name], out[f"answers_{name}"] = acc(cases, a), a
    out["held_split"] = split(HELD, out["answers_held"])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--skip-llm", action="store_true")
    ap.add_argument("--only")
    a = ap.parse_args()
    res_path = HERE / "results.json"
    res = json.loads(res_path.read_text()) if res_path.exists() else {}
    runs = {
        "rapidfuzz (aliasy + pokrycie opcji + reguła)": lambda: run_rapidfuzz(a.db),
        "embeddings intfloat/multilingual-e5-small (CPU)": lambda: run_embeddings("intfloat/multilingual-e5-small", "query: ", "passage: "),
        "embeddings sdadas/mmlw-retrieval-roberta-base (CPU, polski)": lambda: run_embeddings("sdadas/mmlw-retrieval-roberta-base", "zapytanie: ", ""),
        "reranker BAAI/bge-reranker-v2-m3 (CPU)": lambda: run_reranker("BAAI/bge-reranker-v2-m3"),
        "NLI zero-shot MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7 (CPU)": lambda: run_nli("MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"),
        "embeddings Eden cohere/embed-multilingual-v3.0": lambda: run_eden_embeddings("cohere/embed-multilingual-v3.0"),
        "embeddings Eden openai/text-embedding-3-small": lambda: run_eden_embeddings("openai/text-embedding-3-small"),
    }
    if not a.skip_llm:
        runs["LLM Eden mistral/mistral-small-2603"] = lambda: run_llm("mistral/mistral-small-2603", a.db)
        runs["LLM Eden mistral/ministral-8b-2512"] = lambda: run_llm("mistral/ministral-8b-2512", a.db)
    for name, fn in runs.items():
        if a.only and a.only not in name:
            continue
        t = time.perf_counter()
        try:
            res[name] = fn()
        except Exception as e:  # one broken model must not lose the others' results
            res[name] = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
        print(f"{name}: dev {res[name].get('dev')} held {res[name].get('held')} {res[name].get('held_split')} "
              f"thr {res[name].get('threshold')} {res[name].get('ms_per_field')} ms ({time.perf_counter() - t:.0f}s)", flush=True)
        res_path.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for base in [k for k in res if k.startswith(("LLM", "NLI", "embeddings", "reranker")) and "answers_held" in res[k]]:
        res[f"hybryda: rapidfuzz, potem {base}"] = run_hybrid(a.db, res[base]["answers_held"], res[base]["answers_dev"])
        h = res[f"hybryda: rapidfuzz, potem {base}"]
        print(f"hybrid {base}: dev {h['dev']} held {h['held']} {h['held_split']}")
    res_path.write_text(json.dumps(res, ensure_ascii=False, indent=1))
