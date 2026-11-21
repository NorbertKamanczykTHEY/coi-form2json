"""Step [D] after the LLM: FieldTree -> FieldTree (same shape the generator reads) + needs_review.

Only the rules that need the source text live here; the generator does techName collisions, presets -> validators,
show_if -> JSONata, required -> validation (it reads `required = optional_evidence is None`).
"""
import re
import unicodedata
from difflib import SequenceMatcher

from .anchors import src_text
from .tree import Drop, FieldTree

# R2: markers that make a field optional (ADR 0018: required by default)
OPTIONAL = re.compile(r"opcjonaln|nieobowiązkow|nie jest (obowiązkow|wymagan)|fakultatywn|można (dołączyć|załączyć|podać|wpisać)|"
                      r"ewentualn|je[śs]li posiada|je[żz]eli posiada|o ile posiada|w przypadku posiadania|dodatkowe informacje|\buwagi\b", re.I)
MUST_ATTACH = re.compile(r"należy (dołączyć|załączyć)|wymagan[ey] (jest )?(dołączenie|załączenie)", re.I)
# "1) ) Dane nieobowiązkowe." as the parser emits it, or "* Dane …"; "*text*" is Markdown emphasis, not a footnote
FOOTNOTE = re.compile(r"^\s*(\d{1,2}(?=\s*\))|\*{1,3}(?=[\s)]))\s*\)?\s*\)?\s*([^*]{3,200})$", re.S)
EMPTY_ITEM = re.compile(r"^\s*\d{1,2}[.)]\s*(_{3,}\s*)+$")  # "2) ___"
SENTENCE = re.compile(r"(?<=[.;!?])\s+|\n")
LABEL_PRESETS = [(re.compile(r"\bpesel\b", re.I), "pesel"), (re.compile(r"e-?mail", re.I), "email"),
                 (re.compile(r"seria i numer dowodu", re.I), "id_card"), (re.compile(r"data urodzenia", re.I), "birth_date")]


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("ł", "l").replace("Ł", "L")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s)).strip("_")[:60]


def clean_option(o: str) -> str:
    o = re.sub(r"\s*_{3,}.*$", "", o).strip(" :;,-")  # "zaliczyć … z tytułu ___" -> "zaliczyć … z tytułu"
    first = o.split(" ", 1)[0]
    return o if any(c.isupper() for c in first[1:]) else o[:1].upper() + o[1:]  # keep mixed-case names ("eDoręczenia")


def norm_ws(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def grounded(quote: str, text: str, min_ratio: float = 0.8) -> bool:
    q = re.sub(r"\W+", " ", quote.lower()).strip()
    t = re.sub(r"\W+", " ", text.lower())
    if not q:
        return False
    m = SequenceMatcher(None, q, t, autojunk=False).find_longest_match(0, len(q), 0, len(t))
    return m.size / len(q) >= min_ratio


def optional_footnotes(blocks: dict[str, str]) -> dict[str, str]:
    """Footnote marker -> its text, for footnotes that say the data is optional ("1) Dane nieobowiązkowe")."""
    return {m[1]: m[2].strip() for t in blocks.values() if (m := FOOTNOTE.match(t)) and OPTIONAL.search(m[2])}


def _stems(s: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[^\W\d_]{3,}", s.lower())}


def own_segment(source_label: str, text: str, shared: bool) -> str:
    """The part of the field's own blocks that speaks about this field: the sentence sharing most words with its
    source label; a block shared with other fields and without sentences gives only the label itself."""
    parts = [x for x in SENTENCE.split(text) if x.strip()]
    if len(parts) > 1:
        lab = _stems(source_label)
        return max(parts, key=lambda x: len(lab & _stems(x)))
    if not shared:
        return text
    words = re.findall(r"[^\W\d_]{2,}", source_label)  # shared block: from the label up to its fill mark (+ a trailing "(...)")
    m = words and re.search(re.escape(words[0]) + r".*?(_{3,}|☐|$)(\s*\([^)]*\))?", text, re.I | re.S)
    return m[0] if m else source_label


def footnote_evidence(source_label: str, text: str, notes: dict[str, str]) -> str | None:
    """A footnote marker right after the label's last word ("przy ulicy1)___") links the field to that footnote."""
    words = re.findall(r"[^\W\d_]{2,}", source_label)
    if not words:
        return None
    for mark, note in notes.items():
        if re.search(re.escape(words[-1]) + r"\W{0,2}" + re.escape(mark) + (r"\)" if mark.isdigit() else r"(?![^\W\d_])"), text, re.I):
            return note
    return None


def normalize(tree: FieldTree, blocks: dict[str, str]) -> tuple[FieldTree, list[dict]]:
    tree = tree.model_copy(deep=True)
    review: list[dict] = []
    notes = optional_footnotes(blocks)
    cites: dict[str, int] = {}
    for p in tree.pages:
        for s in p.sections:
            for f in s.fields:
                for a in f.src:
                    cites[a] = cites.get(a, 0) + 1
    rename, new_key, seen = {}, {}, set()
    for p in tree.pages:  # key = Polish slug of the label, unique in the whole tree (the generator turns it into techName)
        for s in p.sections:
            for f in s.fields:
                k = slug(f.label) or slug(f.key) or "pole"
                while k in seen:
                    k += "_2"
                seen.add(k)
                rename.setdefault(f.key, k)  # duplicate LLM keys: show_if points at the first one
                new_key[id(f)] = k
    for p in tree.pages:
        for s in p.sections:
            keep = []
            for f in s.fields:
                text = src_text(f.src, blocks) + " " + src_text(s.src, blocks)
                if not re.search(r"[^\W\d_]{2,}", f.source_label):  # "2) ___": no words in the source
                    if f.type == "FILE_UPLOADER" or (f.src and all(EMPTY_ITEM.match(blocks.get(a, "")) for a in f.src)):
                        tree.dropped.append(Drop(reason="empty_slot", src=f.src))  # unnamed list items; the #5 reference skips them
                        continue
                    review.append({"key": new_key[id(f)], "why": "source label has no words"})
                f.key = new_key[id(f)]
                f.options = [clean_option(o) for o in f.options]
                if not f.preset and (hit := next((ps for rx, ps in LABEL_PRESETS if rx.search(f.label + " " + f.source_label)), None)):
                    f.preset = hit
                if f.preset == "birth_date" or re.match(r"data\b", f.label, re.I):
                    f.type = "DATEPICKER"
                # R2/R4 (ADR 0018): required unless the field's own source says otherwise
                own = src_text(f.src, blocks)
                seg = own_segment(f.source_label, own, shared=any(cites[a] > 1 for a in f.src))
                note = footnote_evidence(f.source_label, own, notes)
                found = OPTIONAL.search(f.source_label) or OPTIONAL.search(seg)
                ev = f.optional_evidence
                bare = FOOTNOTE.sub(r"\2", ev or "")  # "1) Dane nieobowiązkowe" -> the footnote text
                if ev and not (OPTIONAL.search(ev) and norm_ws(bare) in norm_ws(seg + " " + (note or "") + " " + s.title)):
                    if not (f.show_if or s.show_if):  # a conditional field is required only while shown: not worth a review
                        review.append({"key": f.key, "why": f"optional marker not confirmed in source: {ev!r}"})
                    ev = None
                ev = ev or note or (found and found[0])
                if f.type == "FILE_UPLOADER" and MUST_ATTACH.search(seg) and not OPTIONAL.search(seg):
                    ev = None
                f.optional_evidence = ev or None
                # Q3: a hint the source does not contain is an AI suggestion, whatever the model claimed
                if f.description:
                    f.description_source = "document" if grounded(f.description, text) else "ai"
                if f.doubt:
                    review.append({"key": f.key, "why": f.doubt})  # R7: stays required, flagged
                keep.append(f)
            s.fields = keep
    for p in tree.pages:
        for s in p.sections:
            for si in [s.show_if] + [f.show_if for f in s.fields] + [c for x in tree.consents for c in x.show_if]:
                if si:
                    si.field = rename.get(si.field, si.field)
                    si.options = [clean_option(o) for o in si.options]
    return tree, review
