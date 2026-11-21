"""Step [D] after the LLM: FieldTree -> FieldTree (same shape the generator reads) + needs_review.

Only the rules that need the source text live here; the generator does techName collisions, presets -> validators,
show_if -> JSONata, required -> validation (it reads `required = optional_evidence is None`).
"""
import re
import unicodedata
from difflib import SequenceMatcher

from .anchors import expand, src_text
from .tree import Drop, FieldTree, FormField, Section, ShowIf

# R2: markers that make a field optional (ADR 0018: required by default)
OPTIONAL = re.compile(r"opcjonaln|nieobowiązkow|nie jest (obowiązkow|wymagan)|fakultatywn|można (dołączyć|załączyć|podać|wpisać)|"
                      r"ewentualn|je[śs]li posiada|je[żz]eli posiada|o ile posiada|w przypadku posiadania|dodatkowe informacje|\buwagi\b", re.I)
MUST_ATTACH = re.compile(r"należy (dołączyć|załączyć)|wymagan[ey] (jest )?(dołączenie|załączenie)", re.I)
# "1) ) Dane nieobowiązkowe." as the parser emits it, or "* Dane …"; "*text*" is Markdown emphasis, not a footnote
FOOTNOTE = re.compile(r"^\s*(\d{1,2}(?=\s*\))|\*{1,3}(?=[\s)]))\s*\)?\s*\)?\s*([^*]{3,200})$", re.S)
# "2) ___", "3) ........", or a bare "2)" when the parser drops the dots (ODS cells, OCR)
EMPTY_ITEM = re.compile(r"^\s*\d{1,2}[.)]\s*([_.…‥·\-–]{2,}\s*)*$")
LIST_ITEM = re.compile(r"^\s*\d{1,2}[.)]")
ATTACH_LIST = re.compile(r"załącz|dołącz", re.I)


def list_heading(t: str) -> bool:
    """The short intro of an attachment list ("w załączeniu:", "Załączniki"), not a paragraph that mentions attaching."""
    t = t.strip(" *_")
    return bool(ATTACH_LIST.search(t)) and not LIST_ITEM.match(t) and (t.endswith(":") or len(t) <= 40)
SIGNATURE = re.compile(r"podpis|pieczęć|pieczątk|^\W*data\W*$|data (sporządzenia|wypełnienia|złożenia)|miejscowość,? (i )?data", re.I)
CONDITIONAL = re.compile(r"\bje[śs]li\b|\bje[żz]eli\b|\bw przypadku\b", re.I)
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


def attachment_slots(blocks: dict[str, str]) -> list[list[str]]:
    """Empty numbered lines of an attachment list ("w załączeniu: 1) X 2) ___ 3) ___"), grouped per list.
    They mean "the applicant may add more attachments", unlike empty lines elsewhere."""
    order, groups = list(blocks), []
    for i, a in enumerate(order):
        if not EMPTY_ITEM.match(blocks[a]) or (groups and a in groups[-1]):
            continue
        j = i
        while j > 0 and LIST_ITEM.match(blocks[order[j - 1]]):
            j -= 1
        k = i
        while k + 1 < len(order) and EMPTY_ITEM.match(blocks[order[k + 1]]):
            k += 1
        if j > 0 and list_heading(blocks[order[j - 1]]):
            groups.append(order[i:k + 1])
    return groups


def attachment_items(blocks: dict[str, str]) -> list[str]:
    """Named numbered items of attachment lists: each one is a document the applicant uploads (or a template attachment)."""
    order, out = list(blocks), []
    for i, a in enumerate(order):
        if not list_heading(blocks[a]):
            continue
        for b in order[i + 1:]:
            if not LIST_ITEM.match(blocks[b]):
                break
            if not EMPTY_ITEM.match(blocks[b]):
                out.append(b)
    return out


def _other_attachments(tree: FieldTree, blocks: dict[str, str], seen: set[str]) -> None:
    """Fields the model made from empty attachment-list lines -> one optional multi-file "Inne załączniki" per list."""
    order = list(blocks)
    for slots in attachment_slots(blocks):
        slot_set = set(slots)
        home = None  # the section holding an upload from the same list, else the last one
        before = set(order[max(0, order.index(slots[0]) - 10):order.index(slots[0])])
        for p in tree.pages:
            for s in p.sections:
                s.fields = [f for f in s.fields if not (f.src and set(expand(f.src, blocks)) <= slot_set)]
                if any(f.type == "FILE_UPLOADER" and set(f.src) & before for f in s.fields):
                    home = s
        if home is None:
            if not tree.pages:
                continue
            if not tree.pages[-1].sections:
                tree.pages[-1].sections.append(Section(title="Załączniki"))
            home = tree.pages[-1].sections[-1]
        head = next((order[i] for i in range(order.index(slots[0]) - 1, -1, -1) if list_heading(blocks[order[i]])), slots[0])
        key = "inne_zalaczniki"
        while key in seen:
            key += "_2"
        seen.add(key)
        home.fields.append(FormField(key=key, label="Inne załączniki", source_label=blocks[head], type="FILE_UPLOADER",
                                     multiple=True, optional_evidence=blocks[slots[0]], src=slots))
        tree.dropped = [d for d in tree.dropped if not (d.src and set(expand(d.src, blocks)) <= slot_set)]


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
                    order = list(blocks)
                    first = expand(f.src[:1], blocks)[:1]
                    above = blocks.get(order[order.index(first[0]) - 1], "") if first and first[0] in blocks and order.index(first[0]) else ""
                    if not re.search(r"[^\W\d_]{3,}", src_text(f.src, blocks) + " " + above):  # a blank line under its label is fine
                        review.append({"key": new_key[id(f)], "why": "etykieta źródłowa bez słów, sprawdź, czego dotyczy pole"})
                f.key = new_key[id(f)]
                if SIGNATURE.search(f.source_label) or SIGNATURE.search(f.label):  # the e-form is signed electronically (standard p. 29)
                    tree.dropped.append(Drop(reason="signature_date", src=f.src))
                    continue
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
                        review.append({"key": f.key, "why": f"model oznaczył pole jako opcjonalne, ale w źródle nie ma znacznika ({ev!r}); zostaje wymagane"})
                    ev = None
                ev = ev or note or (found and found[0])
                if f.type == "FILE_UPLOADER" and MUST_ATTACH.search(seg) and not OPTIONAL.search(seg):
                    ev = None
                f.optional_evidence = ev or None
                # Q3: a hint the source does not contain is an AI suggestion, whatever the model claimed
                if f.description:
                    f.description_source = "document" if grounded(f.description, text) else "ai"
                if CONDITIONAL.search(seg) and not (f.show_if or s.show_if or f.optional_evidence):
                    review.append({"key": f.key, "why": "źródło opisuje pole warunkiem („jeśli…”, „w przypadku…”), a pole nie ma warunku wyświetlania"})
                if f.doubt:
                    review.append({"key": f.key, "why": f.doubt})  # R7: stays required, flagged
                keep.append(f)
            s.fields = keep
    for p in tree.pages:
        for s in p.sections:
            named = {tuple(f.src) for f in s.fields if f.type == "FILE_UPLOADER" and not f.multiple}
            # a model-made "more files" upload over a listed document duplicates it; multiple is set by code only
            s.fields = [f for f in s.fields if not (f.multiple and tuple(f.src) in named)]
            for f in s.fields:
                f.multiple = False
    _other_attachments(tree, blocks, seen)  # after the per-field rules: its optionality comes from the list, not a marker
    for p in tree.pages:
        for s in p.sections:
            for si in [s.show_if] + [f.show_if for f in s.fields]:
                if si:
                    si.field = rename.get(si.field, si.field)
                    si.options = [clean_option(o) for o in si.options]
    for si in [c for x in tree.consents for c in x.show_if]:
        si.field = rename.get(si.field, si.field)
        si.options = [clean_option(o) for o in si.options]
    scope_controls(tree)
    return tree, review


def scope_controls(tree: FieldTree) -> None:
    """A control question (e.g. "is the person an adult") whose every dependent is limited to some options of another
    field (e.g. one kind of application) is shown only for those options too, instead of always being required."""
    owner = {f.key: (s, f) for p in tree.pages for s in p.sections for f in s.fields}
    deps: dict[str, list[list[ShowIf]]] = {}
    for p in tree.pages:
        for s in p.sections:
            if s.show_if:
                deps.setdefault(s.show_if.field, []).append([])
            for f in s.fields:
                if f.show_if:
                    deps.setdefault(f.show_if.field, []).append([s.show_if] if s.show_if else [])
    for c in tree.consents:
        for si in c.show_if:
            deps.setdefault(si.field, []).append([x for x in c.show_if if x is not si])
    for key, others in deps.items():
        if key not in owner:
            continue
        sec, ctl = owner[key]
        if ctl.show_if or sec.show_if or not others or not all(others):
            continue
        fields = {x.field for o in others for x in o if not x.negate}
        if len(fields) == 1 and (v := fields.pop()) != key and all(any(x.field == v and not x.negate for x in o) for o in others):
            opts = list(dict.fromkeys(opt for o in others for x in o if x.field == v for opt in x.options))
            if not (v in owner and set(opts) >= set(owner[v][1].options)):  # all options = always shown anyway
                ctl.show_if = ShowIf(field=v, options=opts)
