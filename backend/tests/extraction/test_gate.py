from coi.extraction.gate import gate
from coi.extraction.tree import Drop, FieldTree

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
    g = gate(t, BLOCKS)
    assert not g["ok"] and any(f.startswith("G3") for f in g["fails"])
    assert any(r.get("anchor") == "p1.b3" for r in g["needs_review"])


def test_signature_slot_in_consent_is_not_a_bad_drop():
    blocks = BLOCKS | {"p1.b5": "Oświadczam, że dane są prawdziwe. Ja niżej podpisany ___", "p1.b6": "___"}
    t = tree()
    t.dropped.append(Drop(reason="consent", src=["p1.b5-p1.b6"]))
    assert gate(t, blocks)["bad_drops"] == []
