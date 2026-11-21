from coi.extraction.gate import gate
from coi.extraction.tree import Addressee, Consent, Drop, FieldTree, FormField, Section, ShowIf

BLOCKS = {"p1.b0": "WNIOSEK o test", "p1.b1": "Sposób: ☐ przelew ☐ gotówka", "p1.b2": "Numer rachunku ___",
          "p1.b3": "Imię i nazwisko ___", "p1.b4": "Pouczenie: art. 1"}


def tree(**over):
    t = {"title": "Wniosek o test", "addressee": None, "applicant_kinds": ["person"], "consents": [],
         "dropped": [{"reason": "title", "src": ["p1.b0"]}, {"reason": "applicant_data", "src": ["p1.b3"]}, {"reason": "legal_info", "src": ["p1.b4"]}],
         "pages": [{"title": "Zwrot", "sections": [{"title": "Sposób", "src": ["p1.b1-p1.b2"], "fields": [
             {"key": "sposob", "label": "Wybierz sposób", "source_label": "Sposób", "type": "RADIO", "options": ["Przelew", "Gotówka"], "src": ["p1.b1"]},
             {"key": "rachunek", "label": "Numer rachunku", "source_label": "Numer rachunku", "type": "TEXT_FIELD", "src": ["p1.b2"],
              "show_if": {"field": "sposob", "options": ["Przelew"]}}]}]}]}
    return FieldTree.model_validate(t | over)


def test_good_tree_passes():
    g = gate(tree(), BLOCKS)
    assert g["ok"], g["fails"]
    assert g["coverage"] == 1.0


def test_objections():
    t = tree()
    t.pages[0].sections[0].fields[1].show_if.options = ["Czek"]  # G4
    t.pages[0].sections[0].fields[0].options = ["Przelew"]  # G5
    t.dropped = [d for d in t.dropped if d.reason != "applicant_data"] + [Drop(reason="legal_info", src=["p1.b3"])]  # G11
    t = FieldTree.model_validate(t.model_dump())
    g = gate(t, BLOCKS)
    assert not g["ok"]
    assert {f[:3] for f in g["fails"]} >= {"G4:", "G5:", "G11"}


def test_uncovered_fill_marks_escalate():
    t = tree(dropped=[{"reason": "title", "src": ["p1.b0"]}])
    assert gate(t, BLOCKS)["ok"]  # only the template-data slot "Imię i nazwisko ___" is uncovered: harmless
    g = gate(t, BLOCKS | {"p1.b5": "Kwota ___"})
    assert not g["ok"] and any(f.startswith("G3") and "p1.b5" in f for f in g["fails"])
    assert not any(r.get("anchor") == "p1.b3" for r in g["needs_review"])  # a template-data slot is no review noise


def test_signature_slot_in_consent_is_not_a_bad_drop():
    blocks = BLOCKS | {"p1.b5": "Oświadczam, że dane są prawdziwe. Ja niżej podpisany ___", "p1.b6": "___"}
    t = tree()
    t.dropped.append(Drop(reason="consent", src=["p1.b5-p1.b6"]))
    assert gate(t, blocks)["bad_drops"] == []


def test_label_without_basis_in_document_rejects_tree():
    t = tree()
    t.pages[0].sections[0].fields.append(FormField(key="nr", label="Numer budynku", source_label="numer budynku", type="TEXT_FIELD", src=["p1.b2"]))
    g = gate(t, BLOCKS)
    assert not g["ok"] and any(f.startswith("G7") for f in g["fails"])
    t.pages[0].sections[0].fields[-1].source_label = "(numer rachunku)"  # paraphrase/brackets of real text: grounded
    assert gate(t, BLOCKS)["ok"]


def test_missing_addressee_rejects_when_document_names_one():
    blocks = BLOCKS | {"p1.b5": "Adresat: Wójt Gminy Testowo"}
    t = tree()
    t.dropped.append(Drop(reason="addressee", src=["p1.b5"]))
    assert any(f.startswith("G13") for f in gate(t, blocks)["fails"])
    t.addressee = Addressee(kind="organ", name="Wójt Gminy Testowo", src=["p1.b5"])
    assert gate(t, blocks)["ok"]


def test_consent_show_if_must_resolve_and_labelled_slot_must_be_covered():
    t = tree()
    t.consents = [Consent(text="Zgoda", show_if=[ShowIf(field="sposob", options=["Czek"])])]
    assert any(f.startswith("G4") and "zgoda 1" in f for f in gate(t, BLOCKS)["fails"])
    t.consents[0].show_if[0].options = ["Gotówka"]
    blocks = BLOCKS | {"p1.b5": "Dodatkowe informacje", "p1.b6": "___", "p1.b7": "___", "p1.b8": "Data i podpis"}
    t.dropped.append(Drop(reason="signature_date", src=["p1.b8"]))
    g = gate(t, blocks)
    assert any(f.startswith("G3") and "p1.b6" in f and "p1.b7" not in f for f in g["fails"])  # b7 is the date/signature slot


def test_person_preset_is_not_flagged_as_template_leak():
    t = tree()
    t.pages[0].sections[0].fields.append(FormField(key="imie", label="Imię", source_label="Imię", type="TEXT_FIELD", preset="first_name", src=["p1.b3"]))
    assert not gate(t, BLOCKS)["template_leaks"]


def test_named_attachment_list_item_needs_an_upload():
    blocks = BLOCKS | {"p1.b5": "W załączeniu:", "p1.b6": "1) zaświadczenie o dochodach", "p1.b7": "2) ___"}
    t = tree()
    t.dropped.append(Drop(reason="empty_slot", src=["p1.b5-p1.b7"]))
    assert any(f.startswith("G14") and "p1.b6" in f for f in gate(t, blocks)["fails"])
    t.pages[0].sections[0].fields.append(FormField(key="z", label="Zaświadczenie", source_label="zaświadczenie o dochodach", type="FILE_UPLOADER", src=["p1.b6"]))
    assert gate(t, blocks)["ok"]


ADDR = {"p1.b0": "WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO", "p1.b1": "Wnoszę o ustalenie numeru porządkowego budynkowi zlokalizowanemu",
        "p1.b2": "w miejscowości___ przy ulicy___", "p1.b3": "nr ewidencyjny działki ___w obrębie ___ (podpis wnioskodawcy)"}


def _addr_tree(fields):
    return FieldTree.model_validate({"title": "Wniosek o ustalenie numeru", "applicant_kinds": ["person"],
                                     "dropped": [{"reason": "title", "src": ["p1.b0"]}],
                                     "pages": [{"title": "Budynek", "sections": [{"title": "Lokalizacja", "src": ["p1.b1-p1.b3"], "fields": [
                                         {"key": k, "label": l, "source_label": l, "type": "TEXT_FIELD", "src": [a]} for k, l, a in fields]}]}]})


def test_each_place_to_fill_in_a_paragraph_needs_its_own_field():
    g = gate(_addr_tree([("m", "w miejscowości", "p1.b2"), ("u", "przy ulicy", "p1.b2"), ("d", "nr ewidencyjny działki", "p1.b3")]), ADDR)
    assert any(f.startswith("G3") and "w obrębie" in f for f in g["fails"]), g["fails"]
    assert any(r["anchor"] == "p1.b3" and r["key"] == "d" for r in g["needs_review"])
    full = _addr_tree([("m", "w miejscowości", "p1.b2"), ("u", "przy ulicy", "p1.b2"), ("d", "nr ewidencyjny działki", "p1.b3"), ("o", "w obrębie", "p1.b3")])
    assert gate(full, ADDR)["ok"], gate(full, ADDR)["fails"]


def test_label_only_in_title_or_running_text_is_not_grounded():
    t = _addr_tree([("m", "w miejscowości", "p1.b2"), ("u", "przy ulicy", "p1.b2"), ("d", "nr ewidencyjny działki", "p1.b3"),
                    ("o", "w obrębie", "p1.b3"), ("n", "numer porządkowy", "p1.b1")])
    g = gate(t, ADDR)
    assert any(f.startswith("G7") and "'n'" in f for f in g["fails"]), g["fails"]


def test_register_extract_dropped_as_template_attachment_passes_g11():
    blocks = BLOCKS | {"p1.b5": "Do wniosku należy dołączyć odpis z KRS lub innego właściwego rejestru."}
    t = tree()
    t.dropped.append(Drop(reason="template_attachment", src=["p1.b5"]))
    assert not gate(t, blocks)["bad_drops"]


def test_correspondence_address_must_not_be_dropped_and_party_section_is_no_leak():
    blocks = BLOCKS | {"p1.b5": "B.4 ADRES DO KORESPONDENCJI (wypełnić tylko gdy inny niż w poz. B.3)", "p1.b6": "17. Kraj 18. Miejscowość 19. Ulica"}
    t = tree()
    t.dropped.append(Drop(reason="applicant_data", src=["p1.b5-p1.b6"]))
    assert any(f.startswith("G15") for f in gate(t, blocks)["fails"])
    t.dropped = t.dropped[:-1]
    t.pages[0].sections.append(Section(title="Adres do korespondencji", party=True, src=["p1.b5"], fields=[
        FormField(key="kraj", label="Kraj", source_label="Kraj", type="TEXT_FIELD", src=["p1.b6"]),
        FormField(key="ulica", label="Ulica", source_label="Ulica", type="TEXT_FIELD", src=["p1.b6"]),
        FormField(key="imie_s", label="Imię", source_label="Imię", type="TEXT_FIELD", src=["p1.b6"]),
        FormField(key="nazwisko_s", label="Nazwisko", source_label="Nazwisko", type="TEXT_FIELD", src=["p1.b6"])]))
    g = gate(t, blocks | {"p1.b6": "17. Kraj 18. Ulica 19. Imię 20. Nazwisko"})
    assert not any(f.startswith(("G15", "G7")) for f in g["fails"]), g["fails"]  # numbered positions ground the labels
    assert not g["template_leaks"]


def fld(key, label, type_="FILE_UPLOADER", src="p1.b5", **kw):
    return FormField(key=key, label=label, source_label=label, type=type_, src=[src], **kw)


def with_section(blocks, *fields, **sec):
    t = tree()
    t.pages[0].sections.append(Section(title=sec.pop("title", "Załączniki"), src=sec.pop("src", ["p1.b5"]), fields=list(fields), **sec))
    return gate(t, BLOCKS | blocks)


def codes(g):
    return {f.split(":")[0] for f in g["fails"]}


def test_g16_exclusive_required_fields_need_show_if_or_optional():
    blocks = {"p1.b5": "Załączniki: plan A (w przypadku zaznaczenia poz. 1) lub plan B (w przypadku zaznaczenia poz. 2)"}
    assert "G16" in codes(with_section(blocks, fld("a", "plan A"), fld("b", "plan B")))
    assert "G16" not in codes(with_section(blocks, fld("a", "plan A", optional_evidence="w przypadku"), fld("b", "plan B", optional_evidence="w przypadku")))


def test_g17_conditional_person_block_must_be_a_section():
    blocks = {"p1.b5": "B.2 DANE OSOBY (wypełnić tylko w przypadku zaznaczenia kratki w poz. 1.2) 5. Nazwisko, imię 6. PESEL"}
    t = tree()
    t.dropped.append(Drop(reason="applicant_data", src=["p1.b5"]))
    assert "G17" in codes(gate(t, BLOCKS | blocks))
    g = with_section(blocks, fld("n", "Nazwisko, imię", "TEXT_FIELD"), fld("p", "PESEL", "TEXT_FIELD"), title="Dane osoby", person_role="third_party",
                     show_if=ShowIf(field="sposob", options=["Przelew"]))
    assert "G17" not in codes(g)


def test_g18_consent_forms_and_declaration_text_block():
    t = tree()
    t.consents = [Consent(text="Oświadczam, że zobowiązany/a jestem.", src=["p1.b4"])]
    assert any("redakcji" in r["why"] for r in gate(t, BLOCKS)["needs_review"])  # wording: review only
    g = with_section({"p1.b5": "Oświadczam, że dane są prawdziwe."}, fld("o", "Oświadczam, że dane są prawdziwe.", "TEXT_BLOCK"))
    assert "G18" in codes(g)


def test_g19_sum_position_needs_number_field():
    blocks = {"p1.b5": "E.4 RAZEM WYSOKOŚĆ OPŁATY 69. SUMA poz. 51 oraz 68"}
    assert "G19" in codes(with_section(blocks, fld("s", "Łączna opłata", "TEXT_FIELD")))
    assert "G19" not in codes(with_section(blocks, fld("s", "Łączna opłata", "NUMBER")))


def test_g20_slash_choice_needs_radio():
    blocks = {"p1.b5": "proszę o wynajem/użyczenie* świetlicy ___"}
    assert "G20" in codes(with_section(blocks, fld("m", "Świetlica", "TEXT_FIELD")))
    assert "G20" not in codes(with_section(blocks, fld("r", "Rodzaj", "RADIO", options=["Wynajem", "Użyczenie"]), fld("m", "Świetlica", "TEXT_FIELD")))


def test_g21_description_contradicting_required():
    blocks = {"p1.b5": "Rasa ___"}
    assert "G21" in codes(with_section(blocks, fld("r", "Rasa", "TEXT_FIELD", description="Pole nieobowiązkowe, jeśli to mieszaniec.")))
    assert "G21" not in codes(with_section(blocks, fld("r", "Rasa", "TEXT_FIELD", description="Np. owczarek.")))


def test_g7_uses_whole_text_when_document_has_no_fill_marks():
    blocks = {"p1.b0": "WNIOSEK", "p1.b1": "Dane do zwrotu", "p1.b2": "Data uiszczenia opłaty"}  # docx fields sat in frames
    t = FieldTree.model_validate({"title": "W", "applicant_kinds": ["person"], "dropped": [{"reason": "title", "src": ["p1.b0"]}],
                                  "pages": [{"title": "P", "sections": [{"title": "S", "src": ["p1.b1"], "fields": [
                                      {"key": "d", "label": "Data uiszczenia opłaty", "source_label": "Data uiszczenia opłaty", "type": "DATEPICKER", "src": ["p1.b2"]}]}]}]})
    assert "G7" not in codes(gate(t, blocks))


def test_g22_attachment_list_is_uploads_not_a_checkbox():
    blocks = {"p1.b5": "Załączniki: ☐ plan ☐ mapa"}
    assert "G22" in codes(with_section(blocks, fld("z", "Wybierz załączniki", "CHECKBOX", options=["Plan", "Mapa"])))
    assert "G22" not in codes(with_section(blocks, fld("p", "Plan"), fld("m", "Mapa")))


def test_g23_exclusive_consents_need_show_if_and_g18_catches_past_masculine():
    t = tree()
    t.consents = [Consent(text="Wyrażam zgodę w imieniu osoby niepełnoletniej.", src=["p1.b4"])]
    assert "G23" in codes(gate(t, BLOCKS))
    t.consents = [Consent(text="Wyrażam zgodę w imieniu osoby niepełnoletniej.", src=["p1.b4"], show_if=[ShowIf(field="sposob", options=["Przelew"])])]
    assert "G23" not in codes(gate(t, BLOCKS))
    t.consents = [Consent(text="Oświadczam, że zobowiązany/a jestem.", src=["p1.b4"])]
    g = gate(t, BLOCKS)
    assert "G18" not in codes(g) and any("redakcji" in r["why"] for r in g["needs_review"])  # wording is review-only


def test_g24_declarations_must_not_be_lost():
    blocks = {"p1.b5": "Oświadczam, że nie wykorzystuję zwierząt do polowań."}
    t = tree()
    t.dropped.append(Drop(reason="legal_info", src=["p1.b5"]))
    assert "G24" in codes(gate(t, BLOCKS | blocks))
    t.consents = [Consent(text="Nie wykorzystuję zwierząt do polowań.", src=["p1.b5"])]
    assert "G24" not in codes(gate(t, BLOCKS | blocks))


def test_g25_case_fee_g26_header_text_block_g27_contact():
    fee = {"p1.b5": "Opłata za wydanie zaświadczenia 17 zł, płatna przed złożeniem wniosku na konto urzędu."}
    t = tree()
    t.dropped.append(Drop(reason="legal_info", src=["p1.b5"]))
    assert "G25" in codes(gate(t, BLOCKS | fee))
    t.case_fee, t.case_fee_src = "17 zł przed złożeniem wniosku", ["p1.b5"]
    assert "G25" not in codes(gate(t, BLOCKS | fee))
    proxy = {"p1.b5": "Opłata skarbowa za pełnomocnictwo 17 zł na konto urzędu."}
    assert "G25" not in codes(gate(tree(dropped=[{"reason": "legal_info", "src": ["p1.b5"]}] + tree().model_dump()["dropped"]), BLOCKS | proxy))
    assert "G26" in codes(with_section({"p1.b5": "Podstawa prawna: art. 6 ustawy"}, fld("pp", "Podstawa prawna", "TEXT_BLOCK")))
    g = with_section({"p1.b5": "Telefon ___ E-mail ___"}, fld("t", "Telefon", "TEXT_FIELD"), fld("e", "E-mail", "TEXT_FIELD"), title="Kontakt")
    assert "G27" in codes(g)
    g = with_section({"p1.b5": "Telefon ___"}, fld("t", "Telefon osoby odpowiedzialnej", "TEXT_FIELD"), title="Osoba")
    assert "G27" not in codes(g)
