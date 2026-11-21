from coi.extraction.gate import gate
from coi.extraction.tree import Addressee, Consent, Drop, FieldTree, FormField, ShowIf

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
