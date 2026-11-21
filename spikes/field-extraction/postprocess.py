"""Code half after the LLM: FieldTree -> FieldTree (same shape the generator reads) + needs_review.

Only the rules that need the source text live here; the generator does techName collisions, presets -> validators,
show_if -> JSONata, required -> validation (it reads `required = optional_evidence is None`).

usage: python3 postprocess.py out/form5.<model>.r1.json   (prints the normalized tree and needs_review)
"""
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher

from tree import FieldTree

OPTIONAL = re.compile(r"opcjonaln|nieobowiązkow|można (dołączyć|załączyć)|ewentualn|dodatkowe informacje|uwagi", re.I)
MUST_ATTACH = re.compile(r"należy (dołączyć|załączyć)", re.I)
LABEL_PRESETS = [(re.compile(r"\bpesel\b", re.I), "pesel"), (re.compile(r"e-?mail", re.I), "email"),
                 (re.compile(r"seria i numer dowodu", re.I), "id_card"), (re.compile(r"data urodzenia", re.I), "birth_date")]
RANGE = re.compile(r"p(\d+)\.b(\d+)-p\1\.b(\d+)")


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("ł", "l").replace("Ł", "L")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s)).strip("_")[:60]


def clean_option(o: str) -> str:
    o = re.sub(r"\s*_{3,}.*$", "", o).strip(" :;,-")  # "zaliczyć … z tytułu ___" -> "zaliczyć … z tytułu"
    return o[:1].upper() + o[1:]


def src_text(anchors: list[str], blocks: dict[str, str]) -> str:
    out = []
    for a in anchors:
        m = RANGE.fullmatch(a)
        out += [blocks.get(f"p{m[1]}.b{i}", "") for i in range(int(m[2]), int(m[3]) + 1)] if m else [blocks.get(a, "")]
    return " ".join(out)


def grounded(quote: str, text: str, min_ratio: float = 0.8) -> bool:
    q = re.sub(r"\W+", " ", quote.lower()).strip()
    t = re.sub(r"\W+", " ", text.lower())
    if not q:
        return False
    m = SequenceMatcher(None, q, t, autojunk=False).find_longest_match(0, len(q), 0, len(t))
    return m.size / len(q) >= min_ratio


def normalize(tree: FieldTree, blocks: dict[str, str]) -> tuple[FieldTree, list[dict]]:
    tree = tree.model_copy(deep=True)
    review: list[dict] = []
    rename, seen = {}, set()
    for p in tree.pages:  # key = Polish slug of the label, unique in the whole tree (the generator turns it into techName)
        for s in p.sections:
            for f in s.fields:
                k = slug(f.label) or slug(f.key) or "pole"
                while k in seen:
                    k += "_2"
                seen.add(k)
                rename[f.key] = k
    for p in tree.pages:
        for s in p.sections:
            keep = []
            for f in s.fields:
                text = src_text(f.src, blocks) + " " + src_text(s.src, blocks)
                if not re.search(r"[^\W\d_]{2,}", f.source_label):  # "2) ___": no words in the source
                    if f.type == "FILE_UPLOADER":
                        continue  # empty attachment slot; the #5 reference skips them
                    review.append({"key": rename[f.key], "why": "source label has no words"})
                f.key = rename[f.key]
                f.options = [clean_option(o) for o in f.options]
                if not f.preset and (hit := next((ps for rx, ps in LABEL_PRESETS if rx.search(f.label + " " + f.source_label)), None)):
                    f.preset = hit
                if f.preset == "birth_date" or re.match(r"data\b", f.label, re.I):
                    f.type = "DATEPICKER"
                # R2: optional only with a marker the source really contains; R4: "należy dołączyć" wins for attachments
                ev = f.optional_evidence
                if ev and not (OPTIONAL.search(ev) and ev.lower().strip(" ()*/") in text.lower()):
                    review.append({"key": f.key, "why": f"optional marker not confirmed in source: {ev!r}"})
                    f.optional_evidence = None
                if f.type == "FILE_UPLOADER" and MUST_ATTACH.search(text):
                    f.optional_evidence = None
                # Q3: a hint the source does not contain is an AI suggestion, whatever the model claimed
                if f.description:
                    f.description_source = "document" if grounded(f.description, text) else "ai"
                if f.doubt:
                    review.append({"key": f.key, "why": f.doubt})  # R7: stays required, flagged
                keep.append(f)
            s.fields = keep
    for p in tree.pages:
        for s in p.sections:
            for si in [s.show_if] + [f.show_if for f in s.fields]:
                if si:
                    si.field = rename.get(si.field, si.field)
                    si.options = [clean_option(o) for o in si.options]
    return tree, review


if __name__ == "__main__":
    from extract import blocks_of

    rec = json.load(open(sys.argv[1]))
    tree, review = normalize(FieldTree.model_validate(rec["tree"]), blocks_of(rec["form"]))
    print(json.dumps({"tree": tree.model_dump(exclude_none=True), "needs_review": review}, ensure_ascii=False, indent=1))
