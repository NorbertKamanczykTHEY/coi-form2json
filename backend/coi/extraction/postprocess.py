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
PAST_READ = re.compile(r"\b([Zz])apoznał(?:em|am)(?:\s*/\s*(?:am|em|[Zz]apoznał(?:em|am)))?\s+się")
SECTION_NUMBER = re.compile(r"^\W*([A-Z](?:\.\d{1,2})*|[IVX]{1,4})[.)]?\s+[^\W\d_]{3,}")  # "D.1 ADRES …", "B DANE …", "II. Dane …"
# Q34: who signs a statement on paper; the applicant's own captions are excluded ("Podpis i pieczątka wnioskodawcy", "(czytelny podpis wnioskodawcy)")
SIGNER = re.compile(r"podpis\w*\s+(?!i\b|wnioskodaw|składając|pełnomocnik|osoby (?:upoważnion|reprezentując)|czytel)([^\W\d_][^\W\d_/ ]+(?:\s*/\s*[^\W\d_]+)*(?:\s+[^\W\d_]{4,})?)", re.I)
STATEMENT_OF = re.compile(r"(?:zgod\w*|oświadczeni\w*)\s+(osoby\s+[^\W\d_]{4,}|tej osoby)", re.I)  # "zgoda osoby odpowiedzialnej"
PROOF = re.compile(r"(dołącz|załącz)\w*.{0,100}(dow[oó]d|potwierdzeni|kopi)\w*.{0,40}(opłat|zapłat|wpłat|uiszcz)|(dow[oó]d|potwierdzeni)\w*.{0,40}(opłat|zapłat|wpłat|uiszcz)\w*.{0,100}(dołącz|załącz)", re.I | re.S)
CONSISTENT = re.compile(r"\b(jest|są) spójn|brak niespójno|nie stwierdzono niespójno|zgodn\w* z treści", re.I)
OTHER_BRANCH = re.compile(r"\binn\w+|\bnie\b|\bbrak\b", re.I)
SLASH_ALT = re.compile(r"(?<![\w/])([^\W\d_]{3,}(?:\s?/\s?[^\W\d_]{3,})+)\s?\*")  # S14: "wynajem/użyczenie*", "a/b/c*"
POS_REF = re.compile(r"(?:w przypadku|je[żz]eli|je[śs]li)\b[^;]{0,60}?(?:\bpoz\.?|pozycj\w*|zaznaczeni\w*)\s*(?:kratki\s+)?(?:w\s+)?(?:poz\.?\s*)?((?:[A-Z]\.)*\d{1,3}(?:\.\d{1,3})*)", re.I)  # needs "poz." or "zaznaczenia"
POS_LIST = re.compile(r"\b(poz(?:ycj\w*|\.)?)\s*(\d{1,3}(?:\s*(?:,|\bi\b|\boraz\b|\blub\b)\s*\d{1,3})*)", re.I)
ADDRESS_PART = re.compile(r"kraj|wojew|powiat|gmin|miejscow|ulic|numer (domu|budynku|lokalu)|nr (domu|lokalu)|kod|poczt|adres|budynk|lokal", re.I)
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
    controls = {si.field for p in tree.pages for s in p.sections for si in [s.show_if, *(f.show_if for f in s.fields)] if si} \
        | {si.field for c in tree.consents for si in c.show_if}
    for p in tree.pages:
        for s in p.sections:
            keep = []
            for f in s.fields:
                orig = f.key
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
                if CONDITIONAL.search(seg) and not (f.show_if or s.show_if or f.optional_evidence or orig in controls):
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
    review += relink_show_if(tree)
    review += rebuild_lost_controls(tree, blocks)
    review += _third_party_statements(tree, blocks, seen)
    review += rebuild_slash_choices(tree, blocks, seen)
    review += branch_show_if(tree, blocks)
    review += position_refs(tree, blocks)
    review += _party_non_address(tree)
    place_controls(tree)
    if tree.case_fee_proof and not PROOF.search(" ".join(blocks.values())):  # R6: a proof upload only when the paper asks to attach it
        tree.case_fee_proof = False
    tree.issues = [i for i in tree.issues if not CONSISTENT.search(i)]  # R15: a warning only for a found inconsistency
    review += _consents(tree)
    if tree.case_fee and re.search(r"pełnomocn", tree.case_fee, re.I) and all(re.search(r"pełnomocn", blocks.get(a, ""), re.I) for a in expand(tree.case_fee_src, blocks) or ["-"]):
        tree.case_fee, tree.case_fee_src, tree.case_fee_proof = None, [], False  # the proxy's 17 zł is in the template, not a case fee
        review.append({"key": None, "why": "opłata za pełnomocnictwo nie jest opłatą za sprawę (case_fee); pominięto"})
    if tree.case_fee:  # every amount must be in the cited source; an invented amount is worse than none
        src = src_text(tree.case_fee_src, blocks)
        amounts = re.findall(r"\d+(?:[,.]\d+)?(?=\s*zł)", tree.case_fee)
        if not src.strip() or not amounts or any(x not in src for x in amounts):
            review.append({"key": None, "why": f"opłata za sprawę bez oparcia w cytowanym fragmencie ({tree.case_fee[:60]!r}); pominięto"})
            tree.case_fee, tree.case_fee_src, tree.case_fee_proof = None, [], False
    for sec in (s for p in tree.pages for s in p.sections if not s.number and s.src):  # G12: the generator splits by the paper's numbering
        first = (expand(sec.src, blocks) or [""])[0]
        i = list(blocks).index(first) if first in blocks else 0
        for head in (blocks.get(first, ""), blocks[list(blocks)[i - 1]] if i else ""):  # the heading, or the block right above the section
            if m := SECTION_NUMBER.match(head):
                sec.number = m[1]
                break
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


def relink_show_if(tree: FieldTree) -> list[dict]:
    """A show_if naming a key that no field has (per-section calls cannot see each other's keys) points at the only
    choice field whose options include all the condition's options."""
    choices = [f for p in tree.pages for s in p.sections for f in s.fields if f.type in ("RADIO", "CHECKBOX", "SELECT")]
    keys = {f.key for p in tree.pages for s in p.sections for f in s.fields}
    conds = [x for p in tree.pages for s in p.sections for x in [s.show_if, *(f.show_if for f in s.fields)] if x]
    conds += [x for c in tree.consents for x in c.show_if]
    review = []
    for si in conds:
        if si.field in keys or not si.options:
            continue
        want = {norm_ws(o).lower() for o in si.options}
        hits = [f for f in choices if want <= {norm_ws(o).lower() for o in f.options}]
        if len(hits) == 1:
            review.append({"key": hits[0].key, "why": f"warunek wyświetlania wskazywał nieistniejące pole {si.field!r}; dopasowany po opcjach"})
            si.field = hits[0].key
    return review


def rebuild_slash_choices(tree: FieldTree, blocks: dict[str, str], seen: set[str]) -> list[dict]:
    """S14 / EVAL-4 R12: a paper choice "x/y*" ("niepotrzebne skreślić") the model lost becomes a required RADIO with the
    words around "/" as options, in the section citing that block (else the first one). Wording that looks cut is reviewed."""
    review = []
    if not tree.pages or not tree.pages[0].sections:
        return review
    skip = {a for d in tree.dropped if d.reason in ("consent", "rodo", "legal_info", "signature_date", "office_use") for a in expand(d.src, blocks)}
    skip |= {a for c in tree.consents for a in expand(c.src, blocks)}
    stem = lambda w: w.strip().lower()[:5]  # noqa: E731
    have = [{stem(o) for o in f.options} for p in tree.pages for x in p.sections for f in x.fields if f.type in ("RADIO", "CHECKBOX", "SELECT")]
    for a, t in blocks.items():
        if a in skip:
            continue
        for m in SLASH_ALT.finditer(t):
            words = [w.strip() for w in m[1].split("/")]
            if any({stem(w) for w in words} <= h for h in have):
                continue
            home = next((x for p in tree.pages for x in p.sections if a in expand(x.src, blocks)), tree.pages[0].sections[0])
            opts = [w[:1].upper() + w[1:] for w in words]
            key = slug("wybierz " + " ".join(words))
            while key in seen:
                key += "_2"
            seen.add(key)
            home.fields.insert(0, FormField(key=key, label="Wybierz: " + " lub ".join(w.lower() for w in words), source_label=m[0], type="RADIO",
                                            options=opts, src=[a]))
            have.append({stem(w) for w in words})
            cut = m.start() == 0 or m.end() >= len(t.rstrip()) or any(len(w) < 4 for w in words)
            review.append({"key": key, "why": "opcje odtworzone z papieru, sprawdź brzmienie" if cut else
                           f"wybór „{m[0]}” z papieru odtworzony jako pole RADIO; sprawdź etykietę"})
    return review


def position_refs(tree: FieldTree, blocks: dict[str, str]) -> list[dict]:
    """A condition naming a paper position ("w przypadku zaznaczenia D.3.33.1", "jeśli TAK w poz. 35") is show_if on the
    field with that number: a trailing ".n" is its n-th option, "TAK"/"NIE" the yes/no option. The paper's explicit
    reference beats the model's guess. Position numbers in descriptions become the referenced fields' labels."""
    review, fields = [], [f for p in tree.pages for s in p.sections for f in s.fields]
    by_num = {f.number.strip().rstrip("."): f for f in fields if f.number}
    def target(ref: str, text: str) -> tuple[FormField, str] | None:
        parts = [x for x in ref.split(".") if x]
        nums = [x for x in parts if x.isdigit()]
        for k in range(len(nums), 0, -1):  # "D.3.33.1": field 33 option 1, else field 1 ...
            head, tail = nums[:k], nums[k:]
            for key in (".".join(head), head[-1]):
                f = by_num.get(key)
                if not f or f.type not in ("RADIO", "CHECKBOX", "SELECT"):
                    continue
                if tail and tail[0].isdigit() and 1 <= int(tail[0]) <= len(f.options):
                    return f, f.options[int(tail[0]) - 1]
                yes = re.search(r"\b(tak|nie)\b", text, re.I)
                if not tail and yes:
                    opt = next((o for o in f.options if o.strip().lower() == yes[1].lower()), None)
                    if opt:
                        return f, opt
                if not tail and {o.lower() for o in f.options} == {"tak", "nie"} and re.search(r"zaznacz", text, re.I):
                    return f, next(o for o in f.options if o.lower() == "tak")
        return None
    for p in tree.pages:
        for s in p.sections:
            for node, text in [(s, src_text(s.src[:1], blocks) + " " + s.title)] + [(f, src_text(f.src, blocks) + " " + (f.description or "")) for f in s.fields]:
                m = POS_REF.search(text)
                hit = m and target(m[1], text[m.start():m.end() + 20])
                if not hit or hit[0] is node:
                    continue
                ctl, opt = hit
                new = ShowIf(field=ctl.key, options=[opt])
                if node.show_if != new and not (node is not s and s.show_if == new):  # a field inside a section already scoped the same way
                    review.append({"key": getattr(node, "key", None), "why": f"warunek z papieru („{m[0][:50]}”) → SHOW {ctl.key} = {opt}; sprawdź"})
                    node.show_if = new
    labels = {n: f.label for n, f in by_num.items()}
    for f in fields:
        for attr in ("description",):
            val = getattr(f, attr)
            if not val:
                continue
            def words(m):
                nums = re.findall(r"\d{1,3}", m[2])
                return ", ".join(f"„{labels[x]}”" for x in nums) if all(x in labels for x in nums) else m[0]
            setattr(f, attr, POS_LIST.sub(words, val))
    return review


def _party_non_address(tree: FieldTree) -> list[dict]:
    """A non-address field in the applicant's address part ("czy nieruchomość ma nadany adres", plot numbers) belongs to
    the subject section it concerns (most shared words), not to the party section."""
    review = []
    subject = [s for p in tree.pages for s in p.sections if not s.party and s.person_role != "third_party"]
    for p in tree.pages:
        for s in p.sections:
            if not s.party or not subject:
                continue
            for f in [f for f in s.fields if not ADDRESS_PART.search(f.label) and f.type != "TEXT_BLOCK"]:
                home = max(subject, key=lambda x: len(_stems(x.title) & _stems(f.label + " " + f.source_label)))
                if not _stems(home.title) & _stems(f.label + " " + f.source_label):
                    continue
                s.fields.remove(f)
                home.fields.append(f)
                review.append({"key": f.key, "why": f"pole spoza adresu przeniesione z sekcji adresu składającego do „{home.title}”"})
    return review


def branch_show_if(tree: FieldTree, blocks: dict[str, str]) -> list[dict]:
    """R2 (EVAL-4): in a section with one choice question, a required field without show_if whose source says
    "w przypadku …" belongs to one branch of that question: 'other' wording ("innej osoby", "nie") -> the
    other / "Nie" option, otherwise the first option. The gate used to only report it."""
    review = []
    for p in tree.pages:
        for s in p.sections:
            radios = [f for f in s.fields if f.type == "RADIO" and len(f.options) >= 2]
            if len(radios) != 1 or s.show_if:
                continue
            ctl = radios[0]
            for f in s.fields[s.fields.index(ctl) + 1:]:
                text = src_text(f.src, blocks)
                if f.show_if or f.optional_evidence or not CONDITIONAL.search(text):
                    continue
                cond = text[CONDITIONAL.search(text).start():][:120]
                other = [o for o in ctl.options if re.match(r"\W*(inn|nie\b|brak)", o, re.I)]
                pick = (other or ctl.options[-1:]) if OTHER_BRANCH.search(cond) else [o for o in ctl.options if o not in other][:1]
                if pick:
                    f.show_if = ShowIf(field=ctl.key, options=pick[:1])
                    review.append({"key": f.key, "why": f"warunek z treści („{cond[:60]}…”) dodany jako SHOW na „{ctl.label}” = {pick[0]}; sprawdź"})
    return review


def place_controls(tree: FieldTree) -> None:
    """R2 (EVAL-4): a yes/no control question stands right before the first section that depends on it, not on the first
    page before the choice of application kind; a code-made one nothing depends on is removed."""
    def deps(k):
        return [(p, i, s) for p in tree.pages for i, s in enumerate(p.sections)
                if (s.show_if and s.show_if.field == k) or any(f.show_if and f.show_if.field == k for f in s.fields)]
    used = {si.field for c in tree.consents for si in c.show_if}
    for p in tree.pages:
        for s in [x for x in p.sections if x.title == "Informacje wstępne"]:  # code-made questions only; the paper's stay put
            moved = False
            for f in [f for f in s.fields if f.type == "RADIO" and {o.lower() for o in f.options} == {"tak", "nie"}]:
                where = deps(f.key)
                if not where and f.key not in used and s.title == "Informacje wstępne":
                    s.fields.remove(f)  # a rebuilt / skeleton question nothing asks for
                    moved = True
                    continue
                tp, ti, ts = where[0] if where else (None, None, None)
                if not where or ts is s or (tp is p and ti == p.sections.index(s) + 1):
                    continue  # already in place: in its dependents' section or right before it
                s.fields.remove(f)
                moved = True
                if ts.show_if:  # the dependent section is hidden by this (or another) question: the question gets its own section
                    tp.sections.insert(ti, Section(title=f.label, fields=[f], show_if=ts.show_if if ts.show_if.field != f.key else None))
                else:
                    ts.fields.insert(0, f)
            if moved and not s.fields:
                p.sections.remove(s)


def _third_party_statements(tree: FieldTree, blocks: dict[str, str], seen: set[str]) -> list[dict]:
    """Q34 (user decision): the logged-in applicant never accepts consents for another person. A statement signed on paper
    by someone else ("Podpis kandydata", "Podpis rodzica/opiekuna prawnego") becomes a FILE_UPLOADER "Oświadczenie <kogo>"
    in that person's section, keeping its condition; a statement of another person the paper asks to attach gets one too."""
    order, review = list(blocks), []
    sections = [s for p in tree.pages for s in p.sections]
    if not sections:
        return review
    def home(heading: str, who: str) -> Section:  # the person's section: the paper's heading names them best, then the signer
        h, w = _stems(heading), _stems(who)
        return max(sections, key=lambda s: (len(_stems(s.title) & h), len(_stems(s.title) & w), s.person_role == "third_party"))
    def upload(who: str, src: list[str], conds: list[ShowIf], heading: str, says: str = "") -> None:
        sec = home(heading, who)
        label = "Oświadczenie " + re.sub(r"\s*/\s*", " lub ", who.strip()).lower()
        rest = [c for c in conds if not (sec.show_if and c.field == sec.show_if.field)]  # the section already scopes that question
        cond = rest[-1] if rest else None
        if len(rest) > 1:
            review.append({"key": None, "why": f"„{label}”: kilka warunków zgody, zostaje ostatni ({cond.field})"})
        twin = next((f for f in sec.fields if f.type == "FILE_UPLOADER" and f.label == label and f.show_if == cond), None)
        what = f"Plik z oświadczeniem podpisanym przez {who.strip().replace('/', ' lub ')}" + (f": {says.strip()}" if says.strip() else ".")
        if twin:  # the paper's 1), 2) statements of one signer are one file
            twin.src = list(dict.fromkeys(twin.src + src))
            if says.strip() and says.strip() not in (twin.description or ""):
                twin.description = (twin.description or what).rstrip(".") + " " + says.strip()
            return
        key = slug(label)
        while key in seen:
            key += "_2"
        seen.add(key)
        sec.fields.append(FormField(key=key, label=label, source_label=heading.strip()[:200] or label, type="FILE_UPLOADER", show_if=cond, src=src,
                                    description=what[:400], description_source="document"))  # the label is code-made, the source is the paper's heading
    keep = []
    for c in tree.consents:
        anchors = [a for a in expand(c.src, blocks) if a in blocks]
        start = order.index(anchors[0]) if anchors else None
        end = order.index(anchors[-1]) if anchors else None
        after = [blocks[a] for a in anchors] + ([blocks[a] for a in order[end + 1:end + 4]] if end is not None else [])  # src may span the caption
        cap = next((m for t in after if (m := SIGNER.search(t))), None)
        if not cap:  # a caption naming the applicant (or none) keeps the consent
            keep.append(c)
            continue
        if start is None:
            heading = ""
        else:  # the consent's own heading; when src starts at its "1) …" text, the block above it
            heading = blocks[order[start]] if not re.match(r"^\s*\d{1,2}\)", blocks[order[start]]) or not start else blocks[order[start - 1]]  # "1) …" is text, "5.1. Zgoda …" a heading
        upload(cap[1], c.src, list(c.show_if), heading, c.text)
    if len(keep) < len(tree.consents):
        review.append({"key": None, "why": f"{len(tree.consents) - len(keep)} zgód innej osoby niż wnioskodawca zamieniono na pliki „Oświadczenie …” (Q34)"})
    tree.consents = keep
    cited_uploads = {a for s in sections for f in s.fields if f.type == "FILE_UPLOADER" for a in expand(f.src, blocks)}
    asked = [(a, m) for a, t in blocks.items() if (m := STATEMENT_OF.search(t)) and re.search(r"załącz|dołącz", t, re.I)]
    if asked and not any(a in cited_uploads for a, _ in asked):
        named = next((m[1] for _, m in asked if not m[1].lower().startswith("tej")), None) or \
            next((m[1] for t in blocks.values() if (m := STATEMENT_OF.search(t)) and not m[1].lower().startswith("tej")), "innej osoby")
        upload(named, [a for a, _ in asked], [], " ".join(blocks[a] for a, _ in asked))
    return review


def _consents(tree: FieldTree) -> list[dict]:
    """G4 (EVAL-3): a personal-data consent duplicates the template's RODO one; a contact-channel consent is voluntary."""
    review, keep = [], []
    for c in tree.consents:
        c.text = PAST_READ.sub(lambda m: m[1] + "apoznaję się", c.text)  # the common 1st-person past form; the rest is review (gate)
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
    yes_no = {"tak", "nie"}
    for k, o in refs.items():  # a lone "Tak" / "Nie" is a yes-no question
        if len(o) == 1 and o[0].strip().lower() in yes_no:
            refs[k] = ["TAK", "NIE"] if o[0].isupper() else ["Tak", "Nie"]  # the condition's option must match exactly (G4)
    lost = [FormField(key=k, label=_label_from_key(k, blocks), source_label=_label_from_key(k, blocks), type="RADIO", options=o)
            for k, o in refs.items() if len(o) >= 2]
    for f in lost:  # right before the first section that depends on it (a page-1 question for a later block confuses)
        at = next(((p, i, sec) for p in tree.pages for i, sec in enumerate(p.sections)
                   if (sec.show_if and sec.show_if.field == f.key) or any(x.show_if and x.show_if.field == f.key for x in sec.fields)), None)
        if at and not (at[2].show_if and at[2].show_if.field == f.key):
            at[2].fields.insert(0, f)  # only some fields depend: the question opens their section
        elif at:
            at[0].sections.insert(at[1], Section(title=f.label, fields=[f]))
        elif tree.pages:
            tree.pages[0].sections.insert(0, Section(title="Informacje wstępne", fields=[f]))
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
