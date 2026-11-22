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
            f("acc2", "Numer konta", src="p1.b6", optional_evidence="fakultatywnie"),
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


def test_empty_attachment_list_lines_are_skipped():
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
    assert set(fs) == {"uzasadnienie", "korekta_deklaracji"}  # no upload from "2) …… 3) ___" (EVAL-3 G3)
    assert {a for d in out.dropped if d.reason == "empty_slot" for a in d.src} == {"p1.b3", "p1.b4", "p1.b6"}


def test_signature_and_date_fields_are_dropped():
    blocks = {"p1.b0": "Data sporządzenia wniosku ___ Podpis i pieczątka wnioskodawcy ___", "p1.b1": "Data urodzenia ___"}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [{"title": "S", "fields": [
        f("d", "Data sporządzenia wniosku", "DATEPICKER", "p1.b0"), f("p", "Podpis i pieczątka wnioskodawcy", "TEXT_BLOCK", "p1.b0"),
        f("m", "Miejscowość i data", src="p1.b0"), f("b", "Data urodzenia", "DATEPICKER", "p1.b1")]}]}]})
    out, _ = normalize(t, blocks)
    assert [x.key for x in out.pages[0].sections[0].fields] == ["data_urodzenia"]
    assert all(d.reason == "signature_date" for d in out.dropped) and len(out.dropped) == 3


def test_control_question_is_scoped_to_its_dependents_variants_and_conditional_label_is_flagged():
    blocks = {"p1.b0": "Adres do korespondencji (jeśli różni się od adresu zamieszkania) ___"}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [
        {"title": "Wstęp", "fields": [f("kind", "Rodzaj", "RADIO", "p1.b0", options=["A", "B", "C"]), f("adult", "Czy pełnoletni", "RADIO", "p1.b0", options=["Tak", "Nie"])]},
        {"title": "Adres", "fields": [f("addr", "Adres do korespondencji", src="p1.b0")]}]}],
        "consents": [{"text": "x", "show_if": [{"field": "kind", "options": ["A"]}, {"field": "adult", "options": ["Tak"]}]},
                     {"text": "y", "show_if": [{"field": "kind", "options": ["B"]}, {"field": "adult", "options": ["Nie"]}]}]})
    out, review = normalize(t, blocks)
    fs = {x.key: x for s in out.pages[0].sections for x in s.fields}
    assert fs["czy_pelnoletni"].show_if.field == "rodzaj" and fs["czy_pelnoletni"].show_if.options == ["A", "B"]
    assert fs["rodzaj"].show_if is None
    assert any(r["key"] == "adres_do_korespondencji" and "warunk" in r["why"] for r in review)


def test_model_upload_over_empty_slots_is_removed():
    blocks = {"p1.b0": "w załączeniu:", "p1.b1": "1) zaświadczenie", "p1.b2": "2) ___", "p1.b3": "3) ___"}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [{"title": "S", "fields": [
        f("z", "Zaświadczenie", "FILE_UPLOADER", "p1.b1", source_label="zaświadczenie"),
        {**f("inne_zalaczniki", "Inne załączniki", "FILE_UPLOADER", "p1.b2", source_label="w załączeniu:", multiple=True,
             optional_evidence="2) ___ 3) ___"), "src": ["p1.b2", "p1.b3"]}]}]}]})
    out, review = normalize(t, blocks)
    assert [x.key for x in out.pages[0].sections[0].fields] == ["zaswiadczenie"] and not review


def test_field_without_src_gets_its_block_and_footnote():
    blocks = {"p1.b0": "w miejscowości___ przy ulicy1)___", "p1.b1": "1) ) Dane nieobowiązkowe."}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [{"title": "S", "fields": [
        {"key": "m", "label": "Miejscowość", "source_label": "w miejscowości___", "type": "TEXT_FIELD"},
        {"key": "u", "label": "Ulica", "source_label": "przy ulicy 1)___", "type": "TEXT_FIELD"}]}]}]})
    out, _ = normalize(t, blocks)
    m, u = out.pages[0].sections[0].fields
    assert m.src == ["p1.b0"] and m.optional_evidence is None
    assert u.src == ["p1.b0"] and u.optional_evidence == "Dane nieobowiązkowe."


def test_register_extract_goes_to_template_and_sets_the_signal():
    blocks = {"p1.b0": "Odpis danych z rejestru", "p1.b1": "Do wniosku należy dołączyć aktualny odpis z Krajowego Rejestru Sądowego lub innego właściwego rejestru.",
              "p1.b2": "Do wniosku należy dołączyć opinię."}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["legal_entity"], "pages": [{"title": "P", "sections": [{"title": "S", "fields": [
        f("k", "Odpis z KRS lub innego rejestru", "FILE_UPLOADER", "p1.b1", source_label="odpis z Krajowego Rejestru Sądowego"),
        f("o", "Opinia", "FILE_UPLOADER", "p1.b2", source_label="opinię")]}]}]})
    out, _ = normalize(t, blocks)
    assert [x.key for x in out.pages[0].sections[0].fields] == ["opinia"]
    assert out.entity_extract_required and out.entity_extract_src == ["p1.b1"]
    assert any(d.reason == "template_attachment" and d.src == ["p1.b1"] for d in out.dropped)


def test_register_signal_without_a_register_in_its_source_is_reset():
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["legal_entity"], "entity_extract_required": True, "entity_extract_src": ["p1.b2"], "pages": []})
    out, review = normalize(t, {"p1.b2": "Do wniosku należy dołączyć opinię."})
    assert not out.entity_extract_required and any("rejestru" in r["why"] for r in review)


def test_lost_control_question_is_rebuilt_from_consent_conditions():
    blocks = {"p1.b0": "Zgoda osoby pełnoletniej", "p1.b1": "Zgoda w imieniu osoby niepełnoletniej"}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [{"title": "S", "fields": [
        f("r", "Rodzaj", "RADIO", "p1.b0", options=["A", "B"])]}]}],
        "consents": [{"text": "x", "show_if": [{"field": "rodzaj", "options": ["A"]}, {"field": "czy_osoba_jest_pelnoletnia", "options": ["Tak"]}]},
                     {"text": "y", "show_if": [{"field": "rodzaj", "options": ["A"]}, {"field": "czy_osoba_jest_pelnoletnia", "options": ["Nie"]}]}]})
    out, review = normalize(t, blocks)
    ctl = out.pages[0].sections[0].fields[0]
    assert (ctl.key, ctl.type, ctl.options, ctl.label) == ("czy_osoba_jest_pelnoletnia", "RADIO", ["Tak", "Nie"], "Czy osoba jest pełnoletnia")
    assert ctl.show_if.field == "rodzaj" and ctl.show_if.options == ["A"]  # scoped like its consents
    assert any(r["key"] == ctl.key for r in review)


def test_unknown_drop_reason_is_coerced():
    from coi.extraction.tree import Drop
    assert Drop.model_validate({"reason": "party_data", "src": ["p1.b1"]}).reason == "legal_info"


def test_self_only_signal_kept_only_with_a_quote_that_says_so():
    def run(text):
        t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "applicant_self_only": True, "applicant_self_only_src": ["p1.b2"], "pages": []})
        return normalize(t, {"p1.b2": text})[0]
    assert run("Wniosek składa się osobiście w urzędzie.").applicant_self_only_src == ["p1.b2"]
    assert run("Wniosek nie może być złożony przez pełnomocnika.").applicant_self_only
    assert not run("Dane wnioskodawcy: imię i nazwisko ___").applicant_self_only


def test_correspondence_address_section_becomes_party_data():
    t = FieldTree.model_validate({"title": "D", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [
        {"title": "Adres do korespondencji", "src": ["p1.b1"], "fields": [{"key": "ulica", "label": "Ulica", "source_label": "Ulica", "type": "TEXT_FIELD", "src": ["p1.b2"]}]},
        {"title": "Dane dziecka", "person_role": "third_party", "src": ["p1.b1"], "fields": []}]}]})
    out, _ = normalize(t, {"p1.b1": "B.4 ADRES DO KORESPONDENCJI", "p1.b2": "Ulica ___"})
    assert [s.party for s in out.pages[0].sections] == [True, False]


def test_consents_bare_data_consent_dropped_channel_consent_optional():
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [], "consents": [
        {"text": "Wyrażam zgodę na przetwarzanie moich danych osobowych.", "src": ["p1.b1"]},
        {"text": "Wyrażam zgodę na przetwarzanie moich danych osobowych. Znam regulamin i akceptuję jego postanowienia.", "src": ["p1.b2"]},
        {"text": "Wyrażam zgodę na otrzymywanie korespondencji na adres e-mail.", "src": ["p1.b3"]}]})
    out, review = normalize(t, {"p1.b1": "x", "p1.b2": "y", "p1.b3": "z"})
    assert [(c.src, c.required) for c in out.consents] == [(["p1.b2"], True), (["p1.b3"], False)]
    assert any(d.reason == "rodo" and d.src == ["p1.b1"] for d in out.dropped) and review


def test_descriptions_without_masks_or_label_paraphrase():
    blocks = {"p1.b0": "Data uiszczenia ___ Nr rachunku ___ Ulica ___ Obręb ___"}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [{"title": "S", "fields": [
        f("d", "Data uiszczenia", "DATEPICKER", "p1.b0") | {"description": "DD-MM-RRRR"},
        f("r", "Numer rachunku", src="p1.b0", source_label="Nr rachunku") | {"description": "w formacie XXXXXXXXXXXXXXXXXXXXXXXXXX"},
        f("u", "Ulica", src="p1.b0") | {"description": "Wpisz nazwę ulicy."},
        f("o", "Obręb", src="p1.b0") | {"description": "Znajdziesz go w wypisie z rejestru gruntów."}]}]}]})
    out, _ = normalize(t, blocks)
    assert [x.description for x in out.pages[0].sections[0].fields] == [None, "Wpisz 26 cyfr numeru rachunku.", None, "Znajdziesz go w wypisie z rejestru gruntów."]


def test_paper_numbering_moves_to_number_and_plain_address_parts_lose_the_preset():
    blocks = {"p1.b0": "D.1 ADRES 26. Miejscowość ___ 27. Kod pocztowy ___ 10 zł stawka ___"}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [{"title": "D.1 Adres nieruchomości", "fields": [
        f("m", "26. Miejscowość", src="p1.b0", preset="address"), f("k", "27. Kod pocztowy", src="p1.b0", preset="address"),
        f("s", "10 zł stawka", "NUMBER", "p1.b0")]}]}]})
    sec = normalize(t, blocks)[0].pages[0].sections[0]
    assert (sec.number, sec.title) == ("D.1", "Adres nieruchomości")
    assert [(x.number, x.label, x.preset) for x in sec.fields] == [("26", "Miejscowość", None), ("27", "Kod pocztowy", None), (None, "10 zł stawka", None)]


def test_past_masculine_reading_form_becomes_present():
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [], "consents": [
        {"text": "Oświadczam, że zapoznałem/am się z regulaminem.", "src": ["p1.b1"]}, {"text": "Zapoznałam/zapoznałem się z warunkami.", "src": ["p1.b2"]}]})
    out, _ = normalize(t, {"p1.b1": "x", "p1.b2": "y"})
    assert [c.text for c in out.consents] == ["Oświadczam, że zapoznaję się z regulaminem.", "Zapoznaję się z warunkami."]


def test_proxy_fee_is_no_case_fee_and_section_number_from_heading():
    blocks = {"p1.b0": "D.1 ADRES NIERUCHOMOŚCI", "p1.b1": "Ulica ___", "p1.b2": "Opłata skarbowa od pełnomocnictwa 17 zł"}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "case_fee": "17 zł za pełnomocnictwo", "case_fee_src": ["p1.b2"],
                                  "pages": [{"title": "P", "sections": [{"title": "Adres", "src": ["p1.b0-p1.b1"], "fields": [f("u", "Ulica", src="p1.b1")]}]}]})
    out, _ = normalize(t, blocks)
    assert out.case_fee is None and out.pages[0].sections[0].number == "D.1"


def test_case_fee_amount_must_be_in_its_source():
    blocks = {"p1.b0": "Opłata skarbowa – 82 zł. Numer konta: 12 3456"}
    def run(fee, src):
        t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "case_fee": fee, "case_fee_src": src, "pages": []})
        return normalize(t, blocks)[0].case_fee
    assert run("Opłata skarbowa 82 zł, konto 12 3456", ["p1.b0"]) and not run("Opłata 50 zł, konto …", ["p1.b0"]) and not run("82 zł", [])


def test_q34_statement_signed_by_another_person_becomes_upload_in_their_section():
    blocks = {"p1.b0": "Dane uczestnika: Imię ___", "p1.b1": "Zgoda w imieniu uczestnika niepełnoletniego",
              "p1.b2": "1) Wyrażam zgodę na udział mojego dziecka.", "p1.b3": "2) Znam regulamin.", "p1.b4": "Data Podpis rodzica/opiekuna prawnego",
              "p1.b5": "Oświadczam, że dane są prawdziwe.", "p1.b6": "(czytelny podpis wnioskodawcy)"}
    cond = {"field": "pelnoletni", "options": ["Nie"]}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [
        {"title": "Dane", "fields": [f("pelnoletni", "Czy uczestnik jest pełnoletni", "RADIO", "p1.b0", options=["Tak", "Nie"])]},
        {"title": "Dane uczestnika", "person_role": "third_party", "fields": [f("imie", "Imię", src="p1.b0")]}]}],
        "consents": [{"text": "Wyrażam zgodę na udział mojego dziecka.", "src": ["p1.b2"], "show_if": [cond]},
                     {"text": "Znam regulamin.", "src": ["p1.b3"], "show_if": [cond]},
                     {"text": "Dane są prawdziwe.", "src": ["p1.b5"]}]})
    out, review = normalize(t, blocks)
    assert [c.text for c in out.consents] == ["Dane są prawdziwe."]  # the applicant's own statement stays a consent
    ups = [x for x in out.pages[0].sections[1].fields if x.type == "FILE_UPLOADER"]
    assert [(u.label, u.show_if.field, u.show_if.options, set(u.src)) for u in ups] == [
        ("Oświadczenie rodzica lub opiekuna prawnego", "czy_uczestnik_jest_pelnoletni", ["Nie"], {"p1.b2", "p1.b3"})]
    assert any("Q34" in r["why"] for r in review)


def test_q34_statement_the_paper_asks_to_attach_gets_an_upload():
    blocks = {"p1.b0": "Osoba odpowiedzialna ___ (w przypadku innej osoby - zgoda osoby odpowiedzialnej)",
              "p1.b1": "Oświadczam, że* (w przypadku innej osoby, zbiorcze oświadczenie tej osoby załączyć do wniosku)"}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [
        {"title": "Osoba odpowiedzialna", "person_role": "third_party", "fields": [f("o", "Imię i nazwisko", src="p1.b0")]}]}]})
    ups = [x for x in normalize(t, blocks)[0].pages[0].sections[0].fields if x.type == "FILE_UPLOADER"]
    assert [u.label for u in ups] == ["Oświadczenie osoby odpowiedzialnej"]


def test_show_if_on_an_unknown_key_is_relinked_by_options():
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [
        {"title": "A", "fields": [f("rodzaj", "Rodzaj nieruchomości", "RADIO", "p1.b0", options=["Jednorodzinna", "Wielolokalowa"])]},
        {"title": "B", "show_if": {"field": "typ_nieruchomosci", "options": ["Wielolokalowa"]}, "fields": [f("m", "Miejsce", src="p1.b1")]}]}]})
    out, review = normalize(t, {"p1.b0": "Rodzaj ☐ jednorodzinna ☐ wielolokalowa", "p1.b1": "Miejsce ___"})
    assert out.pages[0].sections[1].show_if.field == "rodzaj_nieruchomosci" and any("dopasowany" in r["why"] for r in review)


def test_lost_yes_no_control_is_rebuilt_before_its_section():
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [
        {"title": "Wstęp", "fields": [f("a", "A", src="p1.b0")]},
        {"title": "Adres do korespondencji", "show_if": {"field": "adres_inny", "options": ["Tak"]}, "fields": [f("u", "Ulica", src="p1.b1")]}]}]})
    out, review = normalize(t, {"p1.b0": "A ___", "p1.b1": "Adres inny ___ Ulica ___"})
    secs = out.pages[0].sections
    assert [s.title for s in secs][1:] != ["Adres do korespondencji"] and secs[1].fields[0].options == ["Tak", "Nie"]
    assert secs[2].show_if.field == secs[1].fields[0].key and any("odtworzone" in r["why"] for r in review)


def test_r2_branch_field_gets_show_if_on_the_other_option_and_control_is_not_flagged():
    blocks = {"p1.b0": "Osoba odpowiedzialna: wnioskodawca, w przypadku innej osoby niż wnioskodawca ___",
              "p1.b1": "w przypadku innej osoby niż wnioskodawca oświadczenie tej osoby załączyć"}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [
        {"title": "Osoba odpowiedzialna", "person_role": "third_party", "fields": [
            f("kto", "Czy osoba odpowiedzialna to wnioskodawca", "RADIO", "p1.b0", options=["Tak", "Nie"]),
            f("imie", "Imię i nazwisko osoby odpowiedzialnej", src="p1.b0"), f("plik", "Oświadczenie", "FILE_UPLOADER", "p1.b1")]}]}]})
    out, review = normalize(t, blocks)
    fs = {x.key: x for x in out.pages[0].sections[0].fields}
    assert fs["imie_i_nazwisko_osoby_odpowiedzialnej"].show_if.options == ["Nie"] and fs["oswiadczenie"].show_if.options == ["Nie"]
    assert not any(r["key"] == "czy_osoba_odpowiedzialna_to_wnioskodawca" and "warunk" in r["why"] for r in review)


def test_r2_yes_no_control_moves_to_its_section_and_an_unused_intro_one_goes():
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [
        {"title": "Informacje wstępne", "fields": [f("pel", "Czy kandydat jest pełnoletni", "RADIO", "p1.b0", options=["Tak", "Nie"]),
                                                   f("pod", "Czy podopieczny jest pełnoletni", "RADIO", "p1.b0", options=["Tak", "Nie"])]},
        {"title": "Rodzaj", "fields": [f("r", "Rodzaj wniosku", "RADIO", "p1.b0", options=["A", "B"])]},
        {"title": "Kandydat", "fields": [f("i", "Imię", src="p1.b1"), f("z", "Oświadczenie rodzica", "FILE_UPLOADER", "p1.b1", show_if={"field": "pel", "options": ["Nie"]})]}]}]})
    out, _ = normalize(t, {"p1.b0": "Czy ☐ Tak ☐ Nie", "p1.b1": "Imię ___"})
    secs = out.pages[0].sections
    assert [s.title for s in secs] == ["Rodzaj", "Kandydat"] and secs[1].fields[0].key == "czy_kandydat_jest_pelnoletni"


def test_r6_proof_only_when_the_paper_asks_and_r15_no_consistency_warning():
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [], "case_fee": "17 zł, konto 12 3", "case_fee_src": ["p1.b0"],
                                  "case_fee_proof": True, "issues": ["Tytuł jest spójny z treścią.", "Administrator danych to inny urząd niż adresat."]})
    out, _ = normalize(t, {"p1.b0": "Opłata 17 zł, konto 12 3, płatna przed złożeniem wniosku."})
    assert not out.case_fee_proof and out.issues == ["Administrator danych to inny urząd niż adresat."]
    out, _ = normalize(t, {"p1.b0": "Opłata 17 zł, konto 12 3. Do wniosku należy dołączyć dowód uiszczenia opłaty."})
    assert out.case_fee_proof


def test_q34_upload_is_grounded_in_its_heading_and_describes_the_statement():
    blocks = {"p1.b0": "Dane uczestnika: Imię ___", "p1.b1": "Zgoda uczestnika", "p1.b2": "1) Znam regulamin.", "p1.b3": "Data Podpis uczestnika"}
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "pages": [{"title": "P", "sections": [
        {"title": "Dane uczestnika", "person_role": "third_party", "fields": [f("imie", "Imię", src="p1.b0")]}]}],
        "consents": [{"text": "Znam regulamin.", "src": ["p1.b1-p1.b3"]}]})
    up = normalize(t, blocks)[0].pages[0].sections[0].fields[-1]
    assert up.source_label == "Zgoda uczestnika" and "uczestnika" in up.description and "Znam regulamin" in up.description
