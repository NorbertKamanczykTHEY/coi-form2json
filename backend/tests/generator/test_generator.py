import copy
import json
import re
from pathlib import Path

import pytest

from coi import create_app
from coi.extraction.tree import FieldTree
from coi.generator import generate, validate
from coi.make_token import make

from .compare import diff, norm

FIX = Path(__file__).parent / "fixtures"
MATERIALS = Path(__file__).resolve().parents[4] / "materials"
SECRET = "test-secret-at-least-32-bytes-long!!"
H = {"Authorization": f"Bearer {make(SECRET, 'tester')}"}
SHA = "0" * 64


def tree(name: str, **change) -> FieldTree:
    return FieldTree.model_validate(json.loads((FIX / f"{name}.tree.json").read_text()) | change)


def pattern(n: int) -> dict:
    return json.loads(next(MATERIALS.glob(f"{n}. *referencyjny*/konfiguracja_form_*.json")).read_text())


def fields(form):
    for t in form["tabs"]:
        for q in t["questions"]:
            for c in q["field"]["repeatingSectionGrid"]:
                yield t["title"], q["field"], c["field"]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("JWT_SECRET", SECRET)
    mp.setenv("JWT_ALG", "HS256")
    mp.setenv("DATABASE_URL", f"sqlite:///{tmp_path_factory.mktemp('db')}/coi.sqlite")
    for k in ("JWT_ISSUER", "JWT_AUDIENCE"):
        mp.delenv(k, raising=False)
    yield create_app()
    mp.undo()


# Accepted differences (generator.md "Wynik spike'a", Q21, Q22, rozbieżności): REQUIRED per R1-R7, rows = fields + 1,
# "Kontakt i zgody", TERYT_4G_DOWODOWY; #5 also differs from #1 (from which the templates come) in its own "Dane" page.
ALLOWED = [r"/validation:", r"/pos:", r"/questionOrder:", r"^[-+] /Kontakt (i zgody|z urzędem)$", r"TERYT_DOWODOWY' -> 'TERYT_4G_DOWODOWY'"]
ALLOWED_5 = ALLOWED + [r"^[-+] /Dane/q/(dane_podmiotu|oplata_skarbowa_pelnomocnictwo_\d|pelnomocnictwo)/children/\w+$",
                       r"/(searchEnabled|multiLevelTree)$", r"/oplata_info(_1)?/description:", r"/podglad_1/description:",
                       r"/wybierz_jako_kto_wnioskujesz/options:",
                       r"/korekta_deklaracji/description:"]  # FieldTree sections carry no description


@pytest.mark.parametrize("n, prefill, allowed", [(1, "MLPZ", ALLOWED), (5, "PESEL", ALLOWED_5)])
def test_regression_against_patterns(n, prefill, allowed):
    form, rep, _ = generate(tree(f"pattern{n}"), SHA, settings={"prefill_identity": prefill})
    lines = list(diff(norm(pattern(n)), norm(form)))
    assert not [x for x in lines if "/states" in x]  # every JSONata identical
    assert [x for x in lines if not any(re.search(a, x) for a in allowed)] == []
    assert rep["validation"] == [] and rep["warnings"] == []


def test_deterministic_ids_seeded_by_file():
    a, b = (json.dumps(generate(tree("form7"), SHA)[0]) for _ in range(2))
    c = generate(tree("form7"), "1" * 64)[0]
    assert a == b
    assert json.loads(a)["tabs"][0]["id"] != c["tabs"][0]["id"]
    ids = [f["id"] for *_, f in fields(c)]
    assert len(set(ids)) == len(ids) and all(re.fullmatch(r"[0-9a-f-]{36}", i) and i[14] == "4" for i in ids)


def test_person_variant_drops_entity_sections():
    form, *_ = generate(tree("form3"), SHA)  # applicant_kinds: [person]
    techs = {f["techName"] for *_, f in fields(form)}
    assert "nip" not in techs and "plik_z_odpisem_danych" not in techs
    radio = next(f for *_, f in fields(form) if f["techName"] == "wybierz_w_czyim_imieniu_wnioskujesz")
    assert radio["type"] == "RADIO" and [o["name"] for o in radio["options"]] == ["Swoim", "Innej osoby"]


@pytest.mark.parametrize("required", [True, False])
def test_entity_variant_checkbox_from_paper(required):
    t = tree("form1", applicant_kinds=["legal_entity"], entity_option="Klub sportowy")
    form, rep, _ = generate(t, SHA, settings={"entity_required": required})
    box = next(f for *_, f in fields(form) if f["techName"] == "wybierz_w_czyim_imieniu_wnioskujesz")
    assert box["type"] == "CHECKBOX" and [o["name"] for o in box["options"]] == ["Klub sportowy"]
    assert ("REQUIRED" in box["validation"]) is required  # Q31
    shown = [s for _, s, _ in fields(form) if s["techName"] == "dane_podmiotu"][0]
    assert '"Klub sportowy" in' in shown["states"][0]["query"]
    assert "dane_innej_osoby" not in {s["techName"] for _, s, _ in fields(form)}
    assert rep["validation"] == []


def test_addressee_missing_and_consent_from_document():
    t = tree("form3", addressee=None, consents=[{"text": "Oświadczam, że dane są prawdziwe.", "src": ["p1.b9"]}])
    form, rep, _ = generate(t, SHA)
    assert {"key": "addressee", "why": "brak adresata, wstawiono pustą nazwę urzędu"} in rep["needs_review"]
    urzad = next(f for *_, f in fields(form) if f["techName"] == "nazwa_urzedu")
    assert urzad["defaultValue"] == "" and urzad["readOnly"]
    consents = next(f for *_, f in fields(form) if f["type"] == "CONSENT_SECTION")["consentSectionConfig"]["consents"]
    assert consents[-1] == {"description": "<html><head></head><body><p>Oświadczam, że dane są prawdziwe.</p></body></html>", "required": True}


def test_repeating_section_conditions_and_presets():
    t = tree("form7")
    form, rep, fmap = generate(t, SHA)
    dog = next(s for _, s, _ in fields(form) if s["type"] == "REPEATING_SECTION")
    chip = next(c["field"] for c in dog["repeatingSectionGrid"] if c["field"]["techName"] == "dog_microchip_number")
    assert "[$repeatingSectionIndex]['dog_identification_method' in fieldTechName].answers" in chip["states"][0]["query"]
    assert rep["validation"] == []
    assert all(m["src"] for m in fmap.values()) and set(fmap) <= {f["id"] for *_, f in fields(form)}


def test_condition_on_repeating_field_from_outside_is_dropped():
    t = json.loads((FIX / "form7.tree.json").read_text())
    outside = copy.deepcopy(t["pages"][0]["sections"][0]["fields"][0]) | {"key": "x", "type": "TEXT_FIELD", "options": [],
                                                                            "show_if": {"field": "dog_sex", "options": ["suka"]}}
    t["pages"][0]["sections"][0]["fields"].append(outside)
    form, rep, _ = generate(FieldTree.model_validate(t), SHA)
    assert any("sekcji powtarzalnej" in w for w in rep["warnings"])
    assert next(f for *_, f in fields(form) if f["techName"] == "x")["states"] == [] and rep["validation"] == []


@pytest.mark.parametrize("name", ["form1", "form3", "form5", "form7"])
def test_real_trees_with_dictionaries_pass_validator(app, name):
    form, rep, fmap = generate(tree(name), SHA, store=app.config["STORE"])
    assert validate(form) == [] and rep["validation"] == []
    for p in rep["proposed_dictionaries"]:
        assert p["fields"] and p["items"]
        assert all(f["dictionaryName"] == p["id"] for *_, f in fields(form) if f["techName"] in p["fields"])
    phone = next(f for *_, f in fields(form) if f["techName"] == "numer_telefonu")
    assert phone["type"] == "TEXT_FIELD"


def test_validator_on_patterns_and_broken_forms():
    assert validate(pattern(5)) == []
    assert {e["rule"] for e in validate(pattern(1))} == {"R4"}  # #1 has 3 fields with validation: {}
    form = generate(tree("pattern5"), SHA)[0]
    broken = copy.deepcopy(form)
    broken["tabs"] = broken["tabs"][::-1]
    assert "R1" in {e["rule"] for e in validate(broken)}
    broken = copy.deepcopy(form)
    broken["flow"]["links"].pop()
    assert "R5" in {e["rule"] for e in validate(broken)}
    broken = copy.deepcopy(form)
    q = broken["tabs"][1]["questions"][1]["field"]["repeatingSectionGrid"][1]["field"]
    q["states"][0]["query"] = q["states"][0]["query"].replace("Zaliczyć", "Zapłacić")
    nested = copy.deepcopy(broken["tabs"][1]["questions"][0])
    broken["tabs"][1]["questions"][0]["field"]["repeatingSectionGrid"].append(nested)
    finish = broken["tabs"][-1]["questions"][0]["field"]["repeatingSectionGrid"]
    finish.append({"x": 0, "y": 1, "rows": 1, "cols": 3, "field": {**finish[0]["field"], "type": "TEXT_FIELD", "techName": "kwota"}})
    rules = {e["rule"] for e in validate(broken)}
    assert {"R2", "R3", "R6", "techName"} <= rules
    assert validate({"title": 5})[0] == {"path": "/title", "message": "5 is not of type 'string'", "rule": "schema"}


def test_api_validate_and_put_use_rules(app):
    c = app.test_client()
    form = generate(tree("pattern1"), SHA)[0]
    assert c.post("/api/v1/forms/validate", json=form, headers=H).json == {"valid": True, "errors": []}
    bad = c.post("/api/v1/forms/validate", json={"title": "Wniosek", "tabs": [], "flow": {"links": []}}, headers=H).json
    assert not bad["valid"] and bad["errors"][0] == {"path": "/tabs", "message": "a form needs at least 2 tabs", "rule": "R1"}
    fid = app.config["STORE"].add_form(filename="a.docx", sha256=SHA, user="t", form=form, report={}, editor={})
    r = c.put(f"/api/v1/forms/{fid}", json={"title": "Wniosek", "tabs": [], "flow": {"links": []}}, headers=H)
    assert r.status_code == 422 and r.json["errors"][0]["rule"] == "R1"
    assert c.put(f"/api/v1/forms/{fid}", json=form, headers=H).status_code == 200


def test_radio_keeps_its_options(app):
    form, rep, _ = generate(tree("form7"), SHA, store=app.config["STORE"])
    purpose = next(f for *_, f in fields(form) if f["techName"] == "purpose")
    assert purpose["type"] == "RADIO" and len(purpose["options"]) == 8 and "dictionaryName" not in purpose
    assert all(p["source"] != "document" for p in rep["proposed_dictionaries"])
