"""normalize() rules that need the source text (ported from the spike)."""
from coi.extraction.postprocess import normalize
from coi.extraction.tree import FieldTree

BLOCKS = {"p1.b1": "Kwotę proszę: zwrócić przelewem na rachunek ___", "p1.b2": "Telefon (opcjonalnie) ___ Uwagi ___",
          "p1.b3": "2) ___", "p1.b4": "Do wniosku należy dołączyć zaświadczenie. Można dołączyć dyplomy.",
          "p1.b5": "w miejscowości ___ przy ulicy1)___", "p1.b6": "Numer konta ___", "p1.b9": "1) ) Dane nieobowiązkowe.",
          "p1.b7": "Adres (*może być inny niż adres zamieszkania*) ___", "p1.b8": "*Ewentualne uwagi do wniosku*"}


def f(key, label, type_="TEXT_FIELD", src="p1.b2", **kw):
    return {"key": key, "label": label, "source_label": kw.pop("source_label", label), "type": type_, "src": [src], **kw}


def tree():
    return FieldTree.model_validate({
        "title": "Wniosek o test", "addressee": None, "applicant_kinds": ["person"], "consents": [], "dropped": [],
        "pages": [{"title": "Informacje", "sections": [{"title": "Sekcja", "src": [], "fields": [
            f("how", "Wybierz sposób", "RADIO", "p1.b1", options=["zwrócić przelewem na rachunek ___", "zaliczyć"]),
            f("acc", "Numer rachunku", src="p1.b1", show_if={"field": "how", "option": "zwrócić przelewem na rachunek ___"}),
            f("child_pesel", "PESEL dziecka", description="11 cyfr", description_source="document"),
            f("tel2", "Telefon zapasowy", description="Telefon (opcjonalnie)", description_source="ai"),
            f("tel", "Telefon", optional_evidence="opcjonalnie"),
            f("notes", "Uwagi"),
            f("acc2", "Numer konta", src="p1.b6", optional_evidence="nieobowiązkowe"),
            f("city", "Miejscowość", src="p1.b5", source_label="w miejscowości"),
            f("street", "Ulica", src="p1.b5", source_label="przy ulicy"),
            f("dipl", "Dyplomy", "FILE_UPLOADER", "p1.b4", source_label="dyplomy"),
            f("addr", "Adres", src="p1.b7", source_label="Adres"),
            f("slot", "Załącznik 2", "FILE_UPLOADER", "p1.b3", source_label="2) ___"),
            f("cert", "Zaświadczenie", "FILE_UPLOADER", "p1.b4", optional_evidence="Można dołączyć"),
            f("dup", "Telefon"),
        ]}]}],
    })


def test_normalize_rules():
    src = tree()
    out, review = normalize(src, BLOCKS)
    fs = {x.key: x for x in out.pages[0].sections[0].fields}
    assert fs["wybierz_sposob"].options[0] == "Zwrócić przelewem na rachunek"
    assert fs["numer_rachunku"].show_if.field == "wybierz_sposob"
    assert fs["numer_rachunku"].show_if.options == ["Zwrócić przelewem na rachunek"]
    assert fs["pesel_dziecka"].preset == "pesel"
    assert fs["pesel_dziecka"].description_source == "ai"  # Q3: model claimed "document", the source has no such text
    assert fs["telefon_zapasowy"].description_source == "document"
    assert not any(r.get("key") in ("pesel_dziecka", "telefon_zapasowy") for r in review)  # suggestions are not needs_review
    assert fs["telefon"].optional_evidence == "opcjonalnie"  # R2: marker is in the source
    assert fs["uwagi"].optional_evidence == "Uwagi"  # the label itself is a marker
    assert fs["numer_konta"].optional_evidence is None and any(r["key"] == "numer_konta" for r in review)  # invented, flagged
    assert fs["ulica"].optional_evidence == "Dane nieobowiązkowe."  # footnote 1) after the label
    assert fs["miejscowosc"].optional_evidence is None
    assert fs["adres"].optional_evidence is None  # "(*…*)" is emphasis, the italic "*Ewentualne…*" block is no footnote
    assert fs["dyplomy"].optional_evidence == "Można dołączyć"  # its own sentence, not the "należy" one
    assert "zalacznik_2" not in fs and any(d.reason == "empty_slot" and d.src == ["p1.b3"] for d in out.dropped)
    assert fs["zaswiadczenie"].optional_evidence is None  # R4: "należy dołączyć" wins
    assert "telefon_2" in fs  # unique keys
    assert src.pages[0].sections[0].fields[0].key == "how"  # input not mutated


def test_show_if_negate_and_single_option_form():
    t = FieldTree.model_validate({"title": "W", "addressee": None, "applicant_kinds": ["person"], "consents": [], "dropped": [],
                                  "entity_option": "Klub sportowy", "pages": [{"title": "P", "sections": [{"title": "S", "src": [],
                                  "show_if": {"field": "x", "options": ["A"], "negate": True}, "fields": [f("x", "X", "RADIO", options=["A", "B"])]}]}]})
    out, _ = normalize(t, BLOCKS)
    assert out.pages[0].sections[0].show_if.field == "x" and out.pages[0].sections[0].show_if.negate
    assert out.entity_option == "Klub sportowy"


def test_empty_attachment_list_lines_become_one_optional_multi_upload():
    blocks = {"p1.b0": "Uzasadnienie ___", "p1.b1": "w załączeniu:", "p1.b2": "1) korekta deklaracji", "p1.b3": "2) ........",
              "p1.b4": "3) ___", "p1.b5": "Lista uczestników:", "p1.b6": "1) ___"}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"],
                                  "dropped": [{"reason": "empty_slot", "src": ["p1.b3"]}, {"reason": "empty_slot", "src": ["p1.b6"]}],
                                  "pages": [{"title": "P", "sections": [{"title": "S", "fields": [
                                      f("u", "Uzasadnienie", "TEXTAREA", "p1.b0"),
                                      f("k", "Korekta deklaracji", "FILE_UPLOADER", "p1.b2", source_label="korekta deklaracji"),
                                      f("x", "Załącznik 3", "FILE_UPLOADER", "p1.b4", source_label="3) ___")]}]}]})
    out, _ = normalize(t, blocks)
    fs = {x.key: x for x in out.pages[0].sections[0].fields}
    assert fs["korekta_deklaracji"].optional_evidence is None  # the named item stays a required upload
    other = [x for x in fs.values() if x.label == "Inne załączniki"]
    assert len(other) == 1 and other[0].multiple and other[0].type == "FILE_UPLOADER" and other[0].optional_evidence
    assert set(other[0].src) == {"p1.b3", "p1.b4"} and "zalacznik_3" not in fs
    assert [d.src for d in out.dropped] == [["p1.b6"]]  # an empty line of another list stays empty_slot
