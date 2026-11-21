"""Spike: anchored ParsedDocument text -> FieldTree via one Eden call, code-side quality gate, score vs gold_subject.json.

usage (from app/backend): PYTHONPATH=.:../spikes/field-extraction uv run python ../spikes/field-extraction/extract.py <model> [form ...]
Writes out/<form>.<model-slug>.json (tree, gate, score, cost) and appends one line to out/results.jsonl.
"""
import json
import os
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from openai import BadRequestError
from pydantic import ValidationError

from coi import llm
from coi.config import Config
from tree import FieldTree

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
GOLD = json.loads((HERE / "gold_subject.json").read_text())
PROMPT = (HERE / "field_extraction.md").read_text()  # production: app/backend/coi/prompts/field_extraction.md
FILL = re.compile(r"___|☐")
TEMPLATE_LABEL = re.compile(r"^\W*(imi[eę]|nazwisko|pesel|nip|regon|telefon|nr telefonu|numer telefonu|e-?mail|seria i numer dowodu)\b", re.I)
RANGE = re.compile(r"p(\d+)\.b(\d+)-p(\d+)\.b(\d+)")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s/]|_", " ", s)).strip()


def blocks_of(form: str) -> dict[str, str]:
    doc = json.loads((OUT / f"{form}.parsed.json").read_text())
    return {f"p{p['number']}.b{i}": b["text"] for p in doc["pages"] for i, b in enumerate(p["blocks"])}


def expand(anchors: list[str]) -> list[str]:
    out = []
    for a in anchors:
        if m := RANGE.fullmatch(a.strip()):
            p0, b0, p1, b1 = map(int, m.groups())
            out += [f"p{p0}.b{i}" for i in range(b0, b1 + 1)] if p0 == p1 else [a]  # cross-page ranges: not needed for the spike
        else:
            out.append(a.strip().strip("[]"))
    return out


def call(c, model: str, prompt: str, max_tokens: int) -> tuple[str, str, float, float, str]:
    schema = FieldTree.model_json_schema()
    t = time.perf_counter()
    for mode in ("json_schema", "json_object"):
        rf = {"type": "json_schema", "json_schema": {"name": "FieldTree", "schema": schema}} if mode == "json_schema" else {"type": "json_object"}
        try:
            r = c.chat.completions.create(model=model, temperature=0, max_tokens=max_tokens, response_format=rf,
                                          messages=[{"role": "user", "content": prompt}])
            break
        except BadRequestError:  # provider without json_schema support: fall back to json_object + schema in prompt
            if mode == "json_object":
                raise
    extra = (r.model_extra or {}) | ((r.usage and r.usage.model_extra) or {})
    ch = r.choices[0]
    return ch.message.content or "", ch.finish_reason, float(extra.get("cost") or 0), time.perf_counter() - t, mode


def all_fields(tree: FieldTree):
    for p in tree.pages:
        for s in p.sections:
            for f in s.fields:
                yield p, s, f


def neighbours(a: str) -> list[str]:
    m = re.fullmatch(r"p(\d+)\.b(\d+)", a)
    return [f"p{m[1]}.b{int(m[2]) + d}" for d in (-1, 0, 1)] if m else [a]


def gate(tree: FieldTree, blocks: dict[str, str]) -> dict:
    """Checks that need no gold: anchors exist, labels grounded in their blocks, every fill mark cited, show_if resolves."""
    cited, bad_anchor, ungrounded, review = set(), [], [], []
    for d in tree.dropped:
        cited |= set(expand(d.src))
    for c in tree.consents:
        cited |= set(expand(c.src))
    if tree.addressee:
        cited |= set(expand(tree.addressee.src))
    fields = {f.key: f for _, _, f in all_fields(tree)}
    for _, s, f in all_fields(tree):
        src = expand(f.src) + expand(s.src)
        cited |= set(src)
        bad_anchor += [a for a in expand(f.src) if a not in blocks]
        hay = norm(FILL.sub(" ", " ".join(blocks.get(n, "") for a in expand(f.src) for n in neighbours(a))))
        lab = norm(FILL.sub(" ", f.source_label))
        m = SequenceMatcher(None, lab, hay, autojunk=False).find_longest_match(0, len(lab), 0, len(hay)) if lab and hay else None
        if not lab or not m or m.size / len(lab) < 0.7:
            ungrounded.append(f.key)
        if f.doubt:
            review.append({"key": f.key, "why": f.doubt})
    broken_show = []
    for _, s, f in all_fields(tree):
        for owner, si in ((f.key, f.show_if), (s.title, s.show_if)):
            if si and (si.field not in fields or not si.options or any(norm(o) not in {norm(x) for x in fields[si.field].options} for o in si.options)):
                broken_show.append(owner)
    # choice without options; detail field inside a choice's blocks but without show_if (S13 missed)
    no_opts = [f.key for _, _, f in all_fields(tree) if f.type in ("RADIO", "CHECKBOX", "SELECT") and len(f.options) < 2]
    choice_src = {f.key: set(expand(f.src)) for _, _, f in all_fields(tree) if f.type in ("RADIO", "CHECKBOX")}
    orphans = [f.key for _, s, f in all_fields(tree) if f.key not in choice_src and not (f.show_if or s.show_if)
               and any(set(expand(f.src)) <= cs for cs in choice_src.values())]
    review += [{"key": k, "why": "inside a choice block but has no show_if"} for k in orphans]
    # G12: JSONata in COI cannot point from outside a repeating section into it
    in_rep = {f.key for _, sec, f in all_fields(tree) if sec.repeating}
    rep_dep = [f.key for _, sec, f in all_fields(tree) if not sec.repeating and f.show_if and f.show_if.field in in_rep]
    rep_dep += [sec.title for p in tree.pages for sec in p.sections if not sec.repeating and sec.show_if and sec.show_if.field in in_rep]
    # #9: variants copied page by page instead of one section + show_if
    seen, dup_sections = {}, []
    for p in tree.pages:
        for sec in p.sections:
            k = norm(sec.title)
            if k in seen and seen[k] != p.title and not sec.show_if:
                dup_sections.append(sec.title)
            seen.setdefault(k, p.title)
    # applicant/proxy data belongs to the template page "Dane" unless the section is a third party (S9)
    leaks = [f.key for _, sec, f in all_fields(tree) if sec.person_role != "third_party" and TEMPLATE_LABEL.search(f.source_label)]
    review += [{"key": k, "why": "looks like applicant/proxy data (template), not subject"} for k in leaks]
    # G11: a drop reason must fit the block: only template data / signatures / empty slots hold fill marks,
    # and a template attachment is a power of attorney or a fee receipt
    field_src = {a for _, sec, f in all_fields(tree) for a in expand(f.src)}
    bad_drops = [a for d in tree.dropped for a in expand(d.src) if a in blocks and a not in field_src and (
        (d.reason in ("legal_info", "rodo", "title", "template_attachment", "consent") and FILL.search(blocks[a]))
        or (d.reason == "template_attachment" and not re.search(r"pełnomocn|opłat", blocks[a], re.I)))]
    marks = [a for a, t in blocks.items() if FILL.search(t)]
    uncovered = [a for a in marks if a not in cited]
    empty_pages = [p.title for p in tree.pages if not any(s.fields for s in p.sections)]
    cov = round(1 - len(uncovered) / len(marks), 2) if marks else 1.0
    ok = not bad_anchor and not set(broken_show) and not no_opts and len(uncovered) <= len(marks) // 10 and not empty_pages and not dup_sections and not bad_drops and not rep_dep
    review += [{"key": k, "why": "label not found in cited source"} for k in ungrounded]
    review += [{"anchor": a, "why": "fill mark not used by any field or drop"} for a in uncovered]
    return {"ok": ok, "coverage": cov, "bad_anchors": bad_anchor, "ungrounded": ungrounded, "broken_show_if": sorted(set(broken_show)),
            "uncovered": uncovered, "empty_pages": empty_pages, "no_options": no_opts, "orphans": orphans, "dup_sections": sorted(set(dup_sections)), "bad_drops": bad_drops, "repeating_deps": rep_dep, "template_leaks": leaks, "needs_review": review}


def matches(alias: str, f) -> float:
    a = norm(alias)
    best = 0.0
    for lab in (norm(f.label), norm(f.source_label)):
        if not lab:
            continue
        r = SequenceMatcher(None, a, lab).ratio()
        if len(a) >= 5 and (a in lab or (len(lab) >= 5 and lab in a)):
            r = max(r, 0.9)
        best = max(best, r)
    return best


def stems(s: str) -> set[str]:
    return {w[:5] for w in norm(s).split() if len(w) > 2}


def same_option(a: str, b: str) -> bool:
    sa, sb = stems(a), stems(b)
    return bool(sa) and len(sa & sb) / len(sa) >= 0.6


def score(tree: FieldTree, form: str) -> dict:
    g = GOLD.get(form)
    if not g:
        return {}
    ext = [(s, f) for _, s, f in all_fields(tree)]
    used, hit = set(), {}
    for gf in g["fields"]:
        cands = [(max(matches(a, f) for a in gf["aliases"]), i) for i, (s, f) in enumerate(ext) if i not in used]
        if cands and (b := max(cands))[0] >= 0.8:
            used.add(b[1])
            hit[gf["id"]] = ext[b[1]]
    def type_ok(gf, f):
        return f.type == gf["type"] or (f.preset == "address") or ({f.type, gf["type"]} <= {"TEXT_FIELD", "TEXTAREA"})
    types = [type_ok(gf, hit[gf["id"]][1]) for gf in g["fields"] if gf["id"] in hit]
    opts_g = [(o, gf["id"]) for gf in g["fields"] for o in gf.get("options", [])]
    opts_ok = [o for o, i in opts_g if i in hit and any(same_option(o, x) for x in hit[i][1].options)]
    shows = [gf for gf in g["fields"] if gf.get("show_if")]
    def show_ok(gf):
        if gf["id"] not in hit or gf["show_if"] not in hit:
            return False
        s, f = hit[gf["id"]]
        ctl = hit[gf["show_if"]][1].key
        return any(si and si.field == ctl for si in (f.show_if, s.show_if))
    leaks = [f.label for _, f in ext if any(SequenceMatcher(None, norm(l), norm(f.source_label)).ratio() >= 0.9 for l in g["template_leaks"])]
    rep = g.get("repeating")
    return {
        "recall": round(len(hit) / len(g["fields"]), 2),
        "missing": [gf["id"] for gf in g["fields"] if gf["id"] not in hit],
        "type_acc": round(sum(types) / len(types), 2) if types else None,
        "wrong_type": [f"{gf['id']}:{hit[gf['id']][1].type}" for gf in g["fields"] if gf["id"] in hit and not type_ok(gf, hit[gf["id"]][1])],
        "option_recall": round(len(opts_ok) / len(opts_g), 2) if opts_g else None,
        "show_if": f"{sum(map(show_ok, shows))}/{len(shows)}" if shows else None,
        "repeating": all(hit[i][0].repeating for i in rep if i in hit) if rep else None,
        "extra": len(ext) - len(hit),
        "leaks": leaks,
        "consents": len(tree.consents),
    }


def run(model: str, form: str, c, max_tokens: int = int(os.environ.get("MAX_TOKENS", "12000"))) -> dict:
    text = (OUT / f"{form}.anchored.md").read_text()
    prompt = PROMPT.replace("{schema}", json.dumps(FieldTree.model_json_schema(), ensure_ascii=False)).replace("{text}", text)
    rec = {"form": form, "model": model, "run": os.environ.get("RUN", "1"), "cost": 0.0, "secs": 0.0, "chars_in": len(prompt), "repairs": 0}
    msg = prompt
    for attempt in range(2):  # attempt 1 = repair: same model, validation errors appended
        raw, finish, cost, secs, mode = call(c, model, msg, max_tokens)
        rec |= {"mode": mode, "finish": finish, "cost": round(rec["cost"] + cost, 5), "secs": round(rec["secs"] + secs, 1)}
        try:
            body = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
            tree = FieldTree.model_validate_json(body)
            break
        except ValidationError as e:
            rec["repairs"] += 1
            err = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()[:15])
            msg = prompt + f"\n\nPOPRZEDNIA ODPOWIEDŹ BYŁA NIEZGODNA ZE SCHEMATEM ({err}). Popraw ją i zwróć cały JSON:\n{body[:20000]}"
    else:
        rec |= {"schema_ok": False, "error": err[:300]}
        (OUT / f"{form}.{model.replace('/', '_')}.raw.txt").write_text(raw)
        return rec
    rec |= {"schema_ok": True, "pages": [p.title for p in tree.pages], "n_fields": sum(1 for _ in all_fields(tree)),
            "gate": gate(tree, blocks_of(form)), "score": score(tree, form)}
    (OUT / f"{form}.{model.replace('/', '_')}.r{rec['run']}.json").write_text(json.dumps({**rec, "tree": tree.model_dump()}, ensure_ascii=False, indent=1))
    return rec


def regate():
    """Re-run gate + score on saved trees (no LLM calls) -> out/results.jsonl rewritten."""
    lines = []
    for p in sorted(OUT.glob("form*.r*.json")):
        rec = json.loads(p.read_text())
        tree = FieldTree.model_validate(rec.pop("tree"))
        rec |= {"gate": gate(tree, blocks_of(rec["form"])), "score": score(tree, rec["form"])}
        lines.append(json.dumps(rec, ensure_ascii=False))
    fails = [l for l in (OUT / "results.jsonl").read_text().splitlines() if '"schema_ok": false' in l]
    (OUT / "results.jsonl").write_text("\n".join(lines + fails) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "--regate":
        sys.exit(regate())
    model, forms = sys.argv[1], sys.argv[2:] or ["form1", "form5", "form3", "form7"]
    c = llm.provider(Config.load())._client  # shortcut: Provider.chat() has no response_format yet
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(4) as ex:
        for rec in ex.map(lambda f: run(model, f, c), forms):
            g, s = rec.get("gate", {}), rec.get("score", {})
            print(json.dumps({k: rec.get(k) for k in ("form", "model", "mode", "finish", "cost", "secs", "repairs", "schema_ok", "n_fields", "error")}, ensure_ascii=False))
            print("   gate:", {k: g.get(k) for k in ("ok", "coverage", "ungrounded", "broken_show_if", "uncovered", "no_options", "orphans")})
            print("   score:", s)
            with (OUT / "results.jsonl").open("a") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
