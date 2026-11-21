"""Quality gate [C] (code, no gold): accept, repair or escalate. Design §6, checks G2-G12 (G1 = Pydantic, G10 = normalize).

gate() -> {"ok": bool, "fails": [objection, ...] (fed to the repair prompt), "needs_review": [...], "coverage": float, ...}
"""
import re
import unicodedata
from difflib import SequenceMatcher

from .anchors import expand
from .tree import FieldTree

FILL = re.compile(r"___|☐")
TEMPLATE_LABEL = re.compile(r"^\W*((imi[eę]|nazwisko|pesel|nip|regon|telefon|nr telefonu|numer telefonu|e-?mail|seria i numer dowodu)\b"
                            r"|adres( (zamieszkania|siedziby|wnioskodawcy))?\W*$)", re.I)
SIGN_SLOT = re.compile(r"^\W*(___\W*)+$|imi[eę] i nazwisko|podpis|\bdata\b", re.I)  # name/signature/date lines
ORGAN = re.compile(r"\badresat\b|\b(wójt|burmistrz|prezydent miasta|starost[ay]|marszałek|urząd (gminy|miasta|miejski|skarbowy|marszałkowski)|starostwo)\b", re.I)
SIGN_LABEL = re.compile(r"podpis|\bdata\b|miejscowość|imi[eę]|nazwisko|\bnazwa\b|\badres|telefon|e-?mail|pesel|\bnip\b|regon", re.I)  # captions of template data
PERSON_PRESETS = {"first_name", "last_name", "pesel", "birth_date", "id_card", "address", "phone", "email"}
EACH = re.compile(r"dla każdego|każdego (psa|zwierzęcia|dziecka|podopiecznego)", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s/]|_", " ", s)).strip()


def all_fields(tree: FieldTree):
    for p in tree.pages:
        for s in p.sections:
            for f in s.fields:
                yield p, s, f


def gate(tree: FieldTree, blocks: dict[str, str]) -> dict:
    ex = lambda anchors: expand(anchors, blocks)  # noqa: E731
    cited, bad_anchor, ungrounded, review = set(), [], [], []
    doc = norm(FILL.sub(" ", " ".join(blocks.values())))
    for d in tree.dropped:
        cited |= set(ex(d.src))
    for c in tree.consents:
        cited |= set(ex(c.src))
    if tree.addressee:
        cited |= set(ex(tree.addressee.src))
    fields = {f.key: f for _, _, f in all_fields(tree)}
    for _, s, f in all_fields(tree):
        cited |= set(ex(f.src)) | set(ex(s.src))
        bad_anchor += [a for a in ex(f.src) if a not in blocks]
        lab = norm(FILL.sub(" ", f.source_label))
        m = SequenceMatcher(None, lab, doc, autojunk=False).find_longest_match(0, len(lab), 0, len(doc)) if lab else None
        if f.type != "TEXT_BLOCK" and lab and (not m or m.size / len(lab) < 0.7):  # G7: no basis anywhere in the document
            ungrounded.append(f.key)
    broken_show = []  # G4
    for _, s, f in all_fields(tree):
        for owner, si in ((f.key, f.show_if), (s.title, s.show_if)):
            if si and (si.field not in fields or not si.options or any(norm(o) not in {norm(x) for x in fields[si.field].options} for o in si.options)):
                broken_show.append(owner)
    for i, c in enumerate(tree.consents):
        if any(si.field not in fields or not si.options or any(norm(o) not in {norm(x) for x in fields[si.field].options} for o in si.options) for si in c.show_if):
            broken_show.append(f"zgoda {i + 1}")
    broken_show = sorted(set(broken_show))
    no_opts = [f.key for _, _, f in all_fields(tree) if f.type in ("RADIO", "CHECKBOX", "SELECT") and len(f.options) < 2]  # G5
    # G9: detail field inside a choice's blocks but without show_if (S13 missed)
    choice_src = {f.key: set(ex(f.src)) for _, _, f in all_fields(tree) if f.type in ("RADIO", "CHECKBOX")}
    orphans = [f.key for _, s, f in all_fields(tree) if f.key not in choice_src and not (f.show_if or s.show_if)
               and any(set(ex(f.src)) <= cs for cs in choice_src.values())]
    review += [{"key": k, "why": "inside a choice block but has no show_if"} for k in orphans]
    # G12: JSONata in COI cannot point from outside a repeating section into it
    in_rep = {f.key for _, sec, f in all_fields(tree) if sec.repeating}
    rep_dep = [f.key for _, sec, f in all_fields(tree) if not sec.repeating and f.show_if and f.show_if.field in in_rep]
    rep_dep += [sec.title for p in tree.pages for sec in p.sections if not sec.repeating and sec.show_if and sec.show_if.field in in_rep]
    # G6: #9 variants copied page by page instead of one section + show_if
    seen, dup_sections = {}, []
    for p in tree.pages:
        for sec in p.sections:
            k = norm(sec.title)
            if k in seen and seen[k] != p.title and not sec.show_if:
                dup_sections.append(sec.title)
            seen.setdefault(k, p.title)
    dup_sections = sorted(set(dup_sections))
    # G8: applicant/proxy data belongs to the template page "Dane" unless the section is a third party (S9)
    # a person preset means the model placed it as a third party's data (prompt rule); flag one field per section
    leaks = []  # flagged per section, and only for a block of such data (>= 2 fields): one name field is usually someone else's
    for p in tree.pages:
        for sec in p.sections:
            hits = [f.key for f in sec.fields if sec.person_role != "third_party" and f.preset not in PERSON_PRESETS and TEMPLATE_LABEL.search(f.source_label)]
            if len(hits) >= 2:
                leaks.append(hits[0])
    review += [{"key": k, "why": "looks like applicant/proxy data (template), not subject"} for k in leaks]
    # #7: an attachment required "for each" element belongs to the repeating section
    if in_rep:
        review += [{"key": f.key, "why": "attachment 'for each' element is outside the repeating section"}
                   for _, sec, f in all_fields(tree) if f.type == "FILE_UPLOADER" and not sec.repeating
                   and EACH.search(" ".join(blocks.get(a, "") for a in ex(f.src)))]
    # G11: a drop reason must fit the block: only template data / signatures / empty slots hold fill marks,
    # and a template attachment is a power of attorney or a fee receipt
    field_src = {a for _, _, f in all_fields(tree) for a in ex(f.src)}
    bad_drops = [a for d in tree.dropped for a in ex(d.src) if a in blocks and a not in field_src and (
        (d.reason in ("legal_info", "rodo", "title", "template_attachment", "consent") and FILL.search(blocks[a])
         and not (d.reason in ("rodo", "consent") and SIGN_SLOT.search(blocks[a])))
        or (d.reason == "template_attachment" and not re.search(r"pełnomocn|opłat", blocks[a], re.I)))]
    marks = [a for a, t in blocks.items() if FILL.search(t)]
    uncovered = [a for a in marks if a not in cited]  # G3
    order = list(blocks)
    def sign_slot(a):  # signature/date/template-data slots: the label is in the block or, for a bare line, the caption below it
        nxt = blocks.get(order[order.index(a) + 1], "") if order.index(a) + 1 < len(order) else ""
        own = FILL.sub(" ", blocks[a])
        return SIGN_SLOT.search(own) or TEMPLATE_LABEL.search(own) or (not re.search(r"[^\W\d_]{3,}", own) and SIGN_LABEL.search(nxt))
    field_cited = {a for _, sec, f in all_fields(tree) for a in ex(f.src) + ex(sec.src)}
    def label_above(a):  # a bare "___" line under a label block that a field cites belongs to that field
        i = order.index(a)
        return i > 0 and not re.search(r"[^\W\d_]{3,}", blocks[a]) and order[i - 1] in field_cited
    missing = [a for a in uncovered if not sign_slot(a) and not label_above(a)]
    template = {a for d in tree.dropped if d.reason not in ("rodo", "legal_info") for a in ex(d.src)}
    no_addressee = tree.addressee is None and any(ORGAN.search(t) for a, t in blocks.items() if a in template or a not in cited)
    empty_pages = [p.title for p in tree.pages if not any(s.fields for s in p.sections)]
    cov = round(1 - len(missing) / len(marks), 2) if marks else 1.0
    fails = []
    if bad_anchor:
        fails.append(f"G2: nieistniejące kotwice {bad_anchor[:10]}")
    if missing:  # uncovered template-data / signature slots are harmless: the template has those fields
        fails.append(f"G3: miejsca do wpisania (___ lub ☐) bez pola ani dropped; każde z nich to pole przedmiotu albo świadomie usunięty blok szablonu: {missing[:20]}")
    controls = {si.field for _, sec, f in all_fields(tree) for si in (f.show_if, sec.show_if) if si} | {si.field for c in tree.consents for si in c.show_if}
    hard = [k for k in ungrounded if not (k in controls and fields[k].type in ("RADIO", "CHECKBOX", "SELECT"))]  # an added control question has no verbatim label
    if hard:
        fails.append(f"G7: pola bez oparcia w dokumencie (source_label nie występuje w tekście); usuń je albo przepisz source_label dosłownie: {hard[:10]}")
    if no_addressee:
        fails.append("G13: brak `addressee`, choć dokument wskazuje adresata (organ albo urząd); wpisz go do `addressee`")
    if broken_show:
        fails.append(f"G4: show_if wskazuje nieistniejące pole albo opcję (podaj dokładny key i dokładną nazwę opcji): {broken_show[:10]}")
    if no_opts:
        fails.append(f"G5: RADIO/CHECKBOX/SELECT z mniej niż 2 opcjami: {no_opts[:10]}")
    if dup_sections:
        fails.append(f"G6: ta sama sekcja na kilku stronach bez show_if; opisz ją raz i użyj show_if: {dup_sections[:10]}")
    if bad_drops:
        fails.append(f"G11: blok z ___ usunięty z niewłaściwym powodem (powinien być polem przedmiotu): {bad_drops[:10]}")
    if rep_dep:
        fails.append(f"G12: pole spoza sekcji powtarzalnej zależy od pola wewnątrz niej: {rep_dep[:10]}")
    if empty_pages:
        fails.append(f"strony bez pól: {empty_pages}")
    review += [{"key": k, "why": "label not found in the document"} for k in hard]  # added control questions are expected
    review += [{"anchor": a, "why": "fill mark not used by any field or drop"} for a in missing]
    return {"ok": not fails, "fails": fails, "coverage": cov, "needs_review": review, "bad_anchors": bad_anchor, "uncovered": uncovered,
            "broken_show_if": broken_show, "no_options": no_opts, "dup_sections": dup_sections, "bad_drops": bad_drops,
            "repeating_deps": rep_dep, "no_addressee": no_addressee, "empty_pages": empty_pages, "ungrounded": ungrounded, "orphans": orphans, "template_leaks": leaks}
