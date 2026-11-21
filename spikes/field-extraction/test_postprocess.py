"""cd app/backend && uv run python ../spikes/field-extraction/test_postprocess.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from postprocess import normalize  # noqa: E402
from tree import FieldTree  # noqa: E402

blocks = {"p1.b1": "Kwotę proszę: zwrócić przelewem na rachunek ___", "p1.b2": "Telefon (opcjonalnie) ___ Uwagi ___",
          "p1.b3": "2) ___", "p1.b4": "Do wniosku należy dołączyć zaświadczenie. Można dołączyć dyplomy."}


def f(key, label, type_="TEXT_FIELD", src="p1.b2", **kw):
    return {"key": key, "label": label, "source_label": kw.pop("source_label", label), "type": type_, "src": [src], **kw}


tree = FieldTree.model_validate({
    "title": "Wniosek o test", "addressee": None, "applicant_kinds": ["person"], "consents": [], "dropped": [],
    "pages": [{"title": "Informacje", "sections": [{"title": "Sekcja", "src": [], "fields": [
        f("how", "Wybierz sposób", "RADIO", "p1.b1", options=["zwrócić przelewem na rachunek ___", "zaliczyć"]),
        f("acc", "Numer rachunku", src="p1.b1", show_if={"field": "how", "option": "zwrócić przelewem na rachunek ___"}),
        f("child_pesel", "PESEL dziecka", description="11 cyfr", description_source="document"),
        f("tel2", "Telefon zapasowy", description="Telefon (opcjonalnie)", description_source="ai"),
        f("tel", "Telefon", optional_evidence="opcjonalnie"),
        f("notes", "Uwagi", optional_evidence="nieobowiązkowe"),
        f("slot", "Załącznik 2", "FILE_UPLOADER", "p1.b3", source_label="2) ___"),
        f("cert", "Zaświadczenie", "FILE_UPLOADER", "p1.b4", optional_evidence="Można dołączyć"),
    ]}]}],
})
out, review = normalize(tree, blocks)
fs = {x.key: x for x in out.pages[0].sections[0].fields}
assert fs["wybierz_sposob"].options[0] == "Zwrócić przelewem na rachunek", fs["wybierz_sposob"].options
assert fs["numer_rachunku"].show_if.field == "wybierz_sposob" and fs["numer_rachunku"].show_if.options == ["Zwrócić przelewem na rachunek"]
assert fs["pesel_dziecka"].preset == "pesel"
assert fs["pesel_dziecka"].description_source == "ai"  # model claimed "document", the source has no such text
assert fs["telefon_zapasowy"].description_source == "document"  # quoted from the source
assert not any(r["key"] in ("pesel_dziecka", "telefon_zapasowy") for r in review)  # suggestions are not needs_review
assert fs["telefon"].optional_evidence == "opcjonalnie"  # R2: marker is in the source
assert fs["uwagi"].optional_evidence is None and any(r["key"] == "uwagi" for r in review)  # invented marker dropped, flagged
assert "zalacznik_2" not in fs  # empty attachment slot dropped
assert fs["zaswiadczenie"].optional_evidence is None  # R4: "należy dołączyć" in the block wins
assert tree.pages[0].sections[0].fields[0].key == "how"  # input not mutated
print("ok")
