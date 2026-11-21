"""Quality gate [C] (code, no gold): accept, repair or escalate. Design §6, checks G2-G12 (G1 = Pydantic, G10 = normalize).

gate() -> {"ok": bool, "fails": [objection, ...] (fed to the repair prompt), "needs_review": [...], "coverage": float, ...}
"""
import re
import unicodedata
from difflib import SequenceMatcher

from .anchors import expand
from .tree import FieldTree

FILL = re.compile(r"___|☐")
TEMPLATE_LABEL = re.compile(r"^\W*(imi[eę]|nazwisko|pesel|nip|regon|telefon|nr telefonu|numer telefonu|e-?mail|seria i numer dowodu)\b", re.I)
SIGN_SLOT = re.compile(r"^\W*(___\W*)+$|imi[eę] i nazwisko|podpis|niżej podpisan|\bdata\b", re.I)  # name/signature lines under a consent or RODO clause
EACH = re.compile(r"dla każdego|każdego (psa|zwierzęcia|dziecka|podopiecznego)", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s/]|_", " ", s)).strip()


def all_fields(tree: FieldTree):
    for p in tree.pages:
        for s in p.sections:
            for f in s.fields:
                yield p, s, f


def neighbours(a: str) -> list[str]:
    m = re.fullmatch(r"p(\d+)\.b(\d+)", a)
    return [f"p{m[1]}.b{int(m[2]) + d}" for d in (-1, 0, 1)] if m else [a]


def gate(tree: FieldTree, blocks: dict[str, str]) -> dict:
    ex = lambda anchors: expand(anchors, blocks)  # noqa: E731
    cited, bad_anchor, ungrounded, review = set(), [], [], []
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
        hay = norm(FILL.sub(" ", " ".join(blocks.get(n, "") for a in ex(f.src) for n in neighbours(a))))
        lab = norm(FILL.sub(" ", f.source_label))
        m = SequenceMatcher(None, lab, hay, autojunk=False).find_longest_match(0, len(lab), 0, len(hay)) if lab and hay else None
        if not lab or not m or m.size / len(lab) < 0.7:  # G7
            ungrounded.append(f.key)
    broken_show = []  # G4
    for _, s, f in all_fields(tree):
        for owner, si in ((f.key, f.show_if), (s.title, s.show_if)):
            if si and (si.field not in fields or not si.options or any(norm(o) not in {norm(x) for x in fields[si.field].options} for o in si.options)):
                broken_show.append(owner)
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
    leaks = [f.key for _, sec, f in all_fields(tree) if sec.person_role != "third_party" and TEMPLATE_LABEL.search(f.source_label)]
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
    empty_pages = [p.title for p in tree.pages if not any(s.fields for s in p.sections)]
    cov = round(1 - len(uncovered) / len(marks), 2) if marks else 1.0
    fails = []
    if bad_anchor:
        fails.append(f"G2: nieistniejące kotwice {bad_anchor[:10]}")
    if len(uncovered) > len(marks) // 10:
        fails.append(f"G3: bloki z ___ lub ☐ nieprzypisane do żadnego pola ani dropped: {uncovered[:20]}")
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
    review += [{"key": k, "why": "label not found in cited source"} for k in ungrounded]
    review += [{"anchor": a, "why": "fill mark not used by any field or drop"} for a in uncovered]
    return {"ok": not fails, "fails": fails, "coverage": cov, "needs_review": review, "bad_anchors": bad_anchor, "uncovered": uncovered,
            "broken_show_if": broken_show, "no_options": no_opts, "dup_sections": dup_sections, "bad_drops": bad_drops,
            "repeating_deps": rep_dep, "empty_pages": empty_pages, "ungrounded": ungrounded, "orphans": orphans, "template_leaks": leaks}
