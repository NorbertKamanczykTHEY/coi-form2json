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
SELF_ONLY = re.compile(r"osobiście|osobist\w* stawienni|\bnie\b.{0,60}pełnomocni|\bbez\b.{0,20}pełnomocni|wyłącznie przez\b.{0,20}(wnioskodaw|składając)", re.I)
CORRESPONDENCE = re.compile(r"\badres\w*\s+(do|dla)\s+korespondencji\b", re.I)
REGISTER = re.compile(r"(odpis|wyciąg|wypis)\w*\b.{0,40}\b(rejestr\w*|krs|ceidg)\b|\b(krs|ceidg)\b", re.I)
SIGNATURE = re.compile(r"podpis|pieczęć|pieczątk|^\W*data\W*$|data (sporządzenia|wypełnienia|złożenia)|miejscowość,? (i )?data", re.I)
CONDITIONAL = re.compile(r"\bje[śs]li\b|\bje[żz]eli\b|\bw przypadku\b", re.I)
DATA_CONSENT = re.compile(r"przetwarza\w*.{0,80}danych osobowych|danych osobowych.{0,80}przetwarza|ochronie danych osobowych", re.I)
CHANNEL = re.compile(r"e-?mail|\bsms\b|poczty elektronicznej|drogą elektroniczną|środków komunikacji elektronicznej", re.I)
DATE_MASK = re.compile(r"\b(DD|RRRR|YYYY)[-./]|format\w* (daty|dd|rrrr)", re.I)
ACCOUNT_MASK = re.compile(r"X{6,}|\bformacie\b.{0,20}\d{2}", re.I)
GENERIC = {"wpis", "poda", "wybi", "nale", "pros", "pole", "tuta", "któr", "dane", "dany", "nazw", "jest", "tego", "tym"}  # 4-letter stems
LEAD_NUMBER = re.compile(r"^\s*(?:((?:[A-Z]\.)?\d{1,3}(?:\.\d{1,3})*)[.)]|([A-Z](?:\.\d{1,3})+)\.?)\s+(?=\S)")  # "26. Miejscowość", "B.2 Dane"
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


def locate(source_label: str, blocks: dict[str, str]) -> str | None:
    """The first block that contains the label (whitespace and fill marks ignored)."""
    flat = lambda x: re.sub(r"[\W_]+", "", x.lower())  # noqa: E731  "przy ulicy 1)" ~ "przy ulicy1)"
    lab = flat(source_label)
    return next((a for a, t in blocks.items() if lab in flat(t)), None) if len(lab) >= 3 else None


def normalize(tree: FieldTree, blocks: dict[str, str]) -> tuple[FieldTree, list[dict]]:
    tree = tree.model_copy(deep=True)
    review: list[dict] = []
    slot_set = {a for g in attachment_slots(blocks) for a in g}  # G3 (EVAL-3): empty "2) …… 3) ……" lines are skipped, no upload
    for p in tree.pages:
        for s in p.sections:
            s.fields = [f for f in s.fields if not (slot_set and f.src and set(expand(f.src, blocks)) <= slot_set)]
    if lost := sorted(slot_set - {a for d in tree.dropped for a in expand(d.src, blocks)}, key=list(blocks).index):
        tree.dropped.append(Drop(reason="empty_slot", src=lost))
    notes = optional_footnotes(blocks)
    doc_ws = norm_ws(" ".join(blocks.values()))
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
                if f.type == "FILE_UPLOADER" and REGISTER.search(f"{f.label} {f.source_label}"):  # the entity's register extract is in the template
                    tree.dropped.append(Drop(reason="template_attachment", src=f.src))
                    if MUST_ATTACH.search(src_text(f.src, blocks) + " " + f.source_label) and not tree.entity_extract_required:
                        tree.entity_extract_required, tree.entity_extract_src = True, list(f.src)
                    continue
                f.options = [clean_option(o) for o in f.options]
                if m := LEAD_NUMBER.match(f.label):  # G12: the paper's numbering is data for the generator, not label text
                    f.number, f.label = f.number or m[1] or m[2], f.label[m.end():]
                if not f.preset and (hit := next((ps for rx, ps in LABEL_PRESETS if rx.search(f.label + " " + f.source_label)), None)):
                    f.preset = hit
                if f.preset == "birth_date" or re.match(r"data\b", f.label, re.I):
                    f.type = "DATEPICKER"
                if not f.src and (home := locate(f.source_label, blocks)):  # the model left src empty: the block holding the label
                    f.src = [home]
                # R2/R4 (ADR 0018): required unless the field's own source says otherwise
                own = src_text(f.src, blocks)
                seg = own_segment(f.source_label, own, shared=any(cites.get(a, 0) > 1 for a in f.src))
                note = footnote_evidence(f.source_label, f.source_label + " " + own, notes)
                found = OPTIONAL.search(f.source_label) or OPTIONAL.search(seg)
                ev = f.optional_evidence
                bare = FOOTNOTE.sub(r"\2", ev or "")  # "1) Dane nieobowiązkowe" -> the footnote text
                if ev and not (OPTIONAL.search(ev) and norm_ws(bare) in norm_ws(seg + " " + (note or "") + " " + s.title)):
                    # worth a review only for an invented marker; a real one meant for another field changes nothing
                    if not (f.show_if or s.show_if) and norm_ws(bare) not in doc_ws:
                        review.append({"key": f.key, "why": f"model oznaczył pole jako opcjonalne, ale w źródle nie ma znacznika ({ev!r}); zostaje wymagane"})
                    ev = None
                ev = ev or note or (found and found[0])
                if f.type == "FILE_UPLOADER" and MUST_ATTACH.search(seg) and not OPTIONAL.search(seg):
                    ev = None
                f.optional_evidence = ev or None
                # Q3: a hint the source does not contain is an AI suggestion, whatever the model claimed
                if f.description:
                    f.description_source = "document" if grounded(f.description, text) else "ai"
                    f.description = _useful_description(f)
                if CONDITIONAL.search(seg) and not (f.show_if or s.show_if or f.optional_evidence):
                    review.append({"key": f.key, "why": "źródło opisuje pole warunkiem („jeśli…”, „w przypadku…”), a pole nie ma warunku wyświetlania"})
                if f.doubt:
                    review.append({"key": f.key, "why": f.doubt})  # R7: stays required, flagged
                keep.append(f)
            s.fields = keep
            if sum(f.preset == "address" for f in s.fields) > 1:  # an address is ONE preset field; several mean the parts of a plain address
                for f in s.fields:
                    f.preset = None if f.preset == "address" else f.preset
            if m := LEAD_NUMBER.match(s.title):
                s.number, s.title = s.number or m[1] or m[2], s.title[m.end():]
    for p in tree.pages:
        for s in p.sections:
            named = {tuple(f.src) for f in s.fields if f.type == "FILE_UPLOADER" and not f.multiple}
            # a model-made "more files" upload over a listed document duplicates it; multiple is set by code only
            s.fields = [f for f in s.fields if not (f.multiple and tuple(f.src) in named)]
            for f in s.fields:
                f.multiple = False
    for p in tree.pages:
        for s in p.sections:
            for si in [s.show_if] + [f.show_if for f in s.fields]:
                if si:
                    si.field = rename.get(si.field, si.field)
                    si.options = [clean_option(o) for o in si.options]
    for si in [c for x in tree.consents for c in x.show_if]:
        si.field = rename.get(si.field, si.field)
        si.options = [clean_option(o) for o in si.options]
    review += rebuild_lost_controls(tree, blocks)
    review += _consents(tree)
    scope_controls(tree)
    if tree.entity_extract_required and not REGISTER.search(src_text(tree.entity_extract_src, blocks)):
        tree.entity_extract_required, tree.entity_extract_src = False, []  # the model's claim has no register extract in its source
        review.append({"key": None, "why": "model zgłosił wymóg odpisu z rejestru, ale wskazany fragment go nie zawiera; pominięto"})
    for sec in (s for p in tree.pages for s in p.sections if s.person_role != "third_party"):
        if CORRESPONDENCE.search(sec.title + " " + src_text(sec.src, blocks)):
            sec.party = True  # the applicant's correspondence address is party data (page "Dane"), whatever the model flagged
    if tree.applicant_self_only and not SELF_ONLY.search(src_text(tree.applicant_self_only_src, blocks)):
        tree.applicant_self_only, tree.applicant_self_only_src = False, []  # no quote requiring personal action or excluding a proxy
        review.append({"key": None, "why": "model zgłosił, że wniosek składa się tylko osobiście, ale wskazany fragment tego nie mówi; pominięto"})
    return tree, review


def _useful_description(f: FormField) -> str | None:
    """G6/G13 (EVAL-3): no date masks, no 'XXXX' account masks, no AI hint that only rephrases the label."""
    d = f.description or ""
    if f.type == "DATEPICKER" and DATE_MASK.search(d):
        return None
    if ACCOUNT_MASK.search(d) and re.search(r"rachun|konto|iban|nrb", f.label + " " + f.source_label, re.I):
        return "Wpisz 26 cyfr numeru rachunku."
    stems = lambda x: {w[:4] for w in re.findall(r"[^\W\d_]{3,}", x.lower())}  # noqa: E731  "ulicy" ~ "ulica"
    if f.description_source == "ai" and stems(d) <= stems(f.label + " " + f.source_label) | GENERIC:
        return None
    return d or None


def _consents(tree: FieldTree) -> list[dict]:
    """G4 (EVAL-3): a personal-data consent duplicates the template's RODO one; a contact-channel consent is voluntary."""
    review, keep = [], []
    for c in tree.consents:
        if DATA_CONSENT.search(c.text) and "___" not in c.text and len([x for x in SENTENCE.split(c.text) if x.strip()]) == 1:  # only a bare data consent; one with other statements stays
            tree.dropped.append(Drop(reason="rodo", src=c.src))
            review.append({"key": None, "why": f"zgoda na przetwarzanie danych osobowych z dokumentu usunięta (jest w szablonie): {c.text[:80]!r}"})
            continue
        if CHANNEL.search(c.text) and re.search(r"korespondencj|kontakt|powiadom|informacj|doręcz", c.text, re.I):
            c.required = False
        keep.append(c)
    tree.consents = keep
    return review


def _label_from_key(key: str, blocks: dict[str, str]) -> str:
    """'czy_osoba_jest_pelnoletnia' -> 'Czy osoba jest pełnoletnia': each word takes its Polish spelling from the document."""
    words = {slug(w): w.lower() for t in blocks.values() for w in re.findall(r"[^\W\d_]{2,}", t)}
    out = []
    for w in key.split("_"):
        if w in words:
            out.append(words[w])
            continue
        common = lambda k: next((i for i, (a, b) in enumerate(zip(k, w)) if a != b), min(len(k), len(w)))  # noqa: E731
        k = max(words, key=common, default="")
        n = common(k) if k else 0
        out.append(words[k][:n] + w[n:] if n >= 5 else w)  # slug keeps one letter per letter, so the prefix lines up
    return " ".join(out).capitalize()


def rebuild_lost_controls(tree: FieldTree, blocks: dict[str, str]) -> list[dict]:
    """Conditions that name a control question no field asks (a repair dropped it) get that question back as a RADIO
    at the start of the first page, with the options the conditions use; a lone option cannot be rebuilt and is reported."""
    have = {f.key for p in tree.pages for s in p.sections for f in s.fields}
    refs: dict[str, list[str]] = {}
    for si in [c for x in tree.consents for c in x.show_if] + [x for p in tree.pages for s in p.sections for x in [s.show_if, *(f.show_if for f in s.fields)] if x]:
        if si.field not in have:
            refs.setdefault(si.field, []).extend(o for o in si.options if o not in refs.get(si.field, []))
    lost = [FormField(key=k, label=_label_from_key(k, blocks), source_label=_label_from_key(k, blocks), type="RADIO", options=o)
            for k, o in refs.items() if len(o) >= 2]
    if lost and tree.pages:
        tree.pages[0].sections.insert(0, Section(title="Informacje wstępne", fields=lost))
    return [{"key": f.key, "why": "pytanie sterujące odtworzone z warunków zgód lub sekcji; sprawdź etykietę"} for f in lost]


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
