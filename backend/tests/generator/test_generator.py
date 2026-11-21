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
ALLOWED = [r"/validation:", r"/pos:", r"/questionOrder:", r"^[-+] /Kontakt (i zgody|z urzędem)$", r"TERYT_DOWODOWY' -> 'TERYT_4G_DOWODOWY'",
           r"/wojewodztwo\w*/title: 'TERYT_(4G_)?DOWODOWY' -> 'Miejscowość'$"]  # human title instead of the dictionary name
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
    assert {"key": "addressee", "why": "brak adresata, pole nazwy urzędu do uzupełnienia"} in rep["needs_review"]
    urzad = next(f for *_, f in fields(form) if f["techName"] == "nazwa_urzedu")
    assert urzad["defaultValue"] == "" and not urzad["readOnly"] and urzad["validation"] == ["REQUIRED"]  # empty: the applicant types it
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
    for p in rep["proposed_dictionaries"]:  # ADR 0025: proposals go to the report, the field stays as without a dictionary
        assert p["fields"] and p["items"]
        assert all(f.get("dictionaryName") is None for *_, f in fields(form) if f["techName"] in p["fields"])
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


def test_proposal_not_applied_but_ready_for_editor(app):
    store = app.config["STORE"]
    form, rep, fmap = generate(tree("form7"), SHA, store=store)
    breed = next(f for *_, f in fields(form) if f["techName"] == "dog_breed")
    assert breed["type"] == "TEXT_FIELD" and "dictionaryName" not in breed
    assert [p["id"] for p in rep["proposed_dictionaries"]] == ["RASY_PSOW_AGRESYWNYCH"]
    (prop,) = rep["editor_proposals"]
    assert prop["fieldIds"] == [breed["id"]] and prop["dictionary"]["fields"] == ["dog_breed"] and prop["dictionary"]["items"]
    assert prop["changes"][breed["id"]] == {"type": "SELECT", "dictionaryName": "RASY_PSOW_AGRESYWNYCH", "options": [],
                                            "multiLevelTree": False, "searchEnabled": prop["changes"][breed["id"]]["searchEnabled"]}
    # acceptance as the editor does it: dictionary into the catalog, then the form with the field switched to it
    c = app.test_client()
    assert c.post("/api/v1/dictionaries/from-proposal", json=prop["dictionary"], headers=H).status_code == 201
    fid = store.add_form(filename="7.pdf", sha256=SHA, user="t", form=form, report=rep, editor={})
    for *_, f in fields(form):
        f.update(prop["changes"].get(f["id"], {}))
    assert c.put(f"/api/v1/forms/{fid}", json=form, headers=H).status_code == 200
    again, rep2, _ = generate(tree("form7"), SHA, store=store)  # later forms match it as existing
    breed2 = next(f for *_, f in fields(again) if f["techName"] == "dog_breed")
    assert breed2["dictionaryName"] == "RASY_PSOW_AGRESYWNYCH" and rep2["proposed_dictionaries"] == []


def _field(key, label, type_="TEXT_FIELD", **kw):
    return {"key": key, "label": label, "source_label": label, "type": type_, "src": ["p1.b1"], **kw}


def _with_section(name, fields, **change):
    t = json.loads((FIX / f"{name}.tree.json").read_text())
    t["pages"][0]["sections"].append({"title": "Dodatkowe", "fields": fields, "src": ["p1.b1"]})
    return FieldTree.model_validate(t | change)


def test_pesel_field_follows_the_paper():
    t = tree("pattern5", dropped=[{"reason": "applicant_data", "src": ["p1.b4-p1.b5"]}])
    blocks = {"p1.b4": "Imię i nazwisko", "p1.b5": "PESEL *", "p1.b6": "Kwota"}
    techs = lambda f: {x["techName"]: x for *_, x in fields(f)}
    asked = techs(generate(t, SHA, blocks=blocks)[0])["numer_pesel"]
    assert asked["validation"] == ["PESEL"] and asked["defaultValue"] == "PESEL.pesel"  # read-only prefill: not REQUIRED
    assert "numer_pesel" not in techs(generate(t, SHA, blocks={"p1.b5": "Adres"})[0])


def test_validators_from_label_wording():
    t = _with_section("form3", [_field("skrzynka", "Adres skrzynki ePUAP"), _field("ade", "Adres do e-Doręczeń"),
                                _field("dowod", "Seria i numer dowodu osobistego"), _field("nip_firmy", "NIP firmy"),
                                _field("uwagi", "Uwagi", "TEXTAREA")])
    got = {f["techName"]: f["validation"] for *_, f in fields(generate(t, SHA)[0])}
    assert got["skrzynka"] == ["REQUIRED", "EPUAP"] and got["ade"] == ["REQUIRED", "ADE"]
    assert got["dowod"] == ["REQUIRED", "SERIAL_NUMBER_ID_CARD"] and got["nip_firmy"] == ["REQUIRED", "NIP"] and got["uwagi"] == ["REQUIRED"]


def test_entity_data_in_subject_is_not_duplicated():
    t = _with_section("form3", [_field("nazwa_klubu", "Nazwa klubu"), _field("adres_siedziby", "Adres siedziby", preset="address"),
                                _field("telefon_klubu", "Telefon kontaktowy")], applicant_kinds=["legal_entity"])
    form, rep, _ = generate(t, SHA)
    techs = {f["techName"] for *_, f in fields(form)}
    assert "telefon_klubu" in techs and "nazwa_klubu" not in techs and not any("adres_siedziby" in x and x != "adres_siedziby" for x in techs)
    assert {"nazwa", "kraj_siedziba"} <= techs and any("powtarzają dane podmiotu" in w for w in rep["warnings"])
    person = generate(_with_section("form3", [_field("adres_siedziby", "Adres siedziby", preset="address")]), SHA)[0]
    assert "kraj_adres_siedziby" in {f["techName"] for *_, f in fields(person)}  # only the entity applicant's own data merges


def test_controlling_field_comes_first():
    t = _with_section("form3", [_field("inny_adres", "Adres do korespondencji", show_if={"field": "czy_inny", "options": ["Tak"]}),
                                _field("czy_inny", "Czy adres do korespondencji jest inny", "RADIO", options=["Tak", "Nie"])])
    sec = next(s for _, s, _ in fields(generate(t, SHA)[0]) if s["title"] == "Dodatkowe")
    assert [c["field"]["techName"] for c in sec["repeatingSectionGrid"]] == ["czy_inny", "inny_adres"]
    assert [c["y"] for c in sec["repeatingSectionGrid"]] == [0, 1]


def test_conditional_consents_get_their_own_show():
    t = _with_section("form3", [_field("pelnoletni", "Czy kandydat jest pełnoletni", "RADIO", options=["Tak", "Nie"])],
                      consents=[{"text": "Oświadczam, że dane są prawdziwe.", "src": []},
                                {"text": "Zgoda rodzica.", "show_if": [{"field": "pelnoletni", "options": ["Nie"]}], "src": []}])
    form, rep, _ = generate(t, SHA)
    consent = [f for *_, f in fields(form) if f["type"] == "CONSENT_SECTION"]
    assert len(consent) == 2 and consent[0]["states"] == [] and len(consent[0]["consentSectionConfig"]["consents"]) == 2
    assert '"Nie" in' in consent[1]["states"][0]["query"] and "'pelnoletni' in field.techName" in consent[1]["states"][0]["query"]
    assert rep["validation"] == []


def test_validator_rejects_empty_required_read_only():
    form = generate(tree("pattern1"), SHA)[0]
    f = next(x for *_, x in fields(form) if x["techName"] == "miejscowosc")
    f |= {"readOnly": True, "validation": ["REQUIRED"], "defaultValue": ""}
    assert [e["rule"] for e in validate(form)] == ["readOnly"]


def test_street_required_unless_the_paper_says_optional():
    t = _with_section("form3", [_field("adres_robot", "Adres robót", preset="address"),
                                _field("adres_opc", "Adres dodatkowy", preset="address", optional_evidence="(jeśli dotyczy)")])
    v = {f["techName"]: f["validation"] for *_, f in fields(generate(t, SHA)[0])}
    assert all("REQUIRED" in v[k] for k in ("ulica", "ulica_zagranica", "ulica_inna_osoba", "ulica_adres_robot"))
    assert v["ulica_adres_opc"] == [] and v["numer_lokalu"] == []  # a flat number stays optional: not every address has one


def test_pesel_read_from_source_text():
    has = lambda t, b: any(f["techName"] == "numer_pesel" for *_, f in fields(generate(t, SHA, blocks=b)[0]))
    assert has(tree("pattern5"), {"p1.b2": "Imię i nazwisko / nazwa", "p1.b3": "PESEL/NIP"})  # nothing dropped as applicant_data
    rodo = tree("pattern5", dropped=[{"reason": "rodo", "src": ["p1.b9"]}])
    assert not has(rodo, {"p1.b9": "Przetwarzamy imię, nazwisko i PESEL."})
    third = _with_section("pattern5", [_field("pesel_dziecka", "PESEL dziecka", preset="pesel", src=["p1.b4"])])
    assert not has(third, {"p1.b4": "PESEL dziecka"})


def test_datepicker_gets_no_text_default():
    t = _with_section("form3", [_field("data_wniosku", "Data", "DATEPICKER", default_value="Data bieżąca (automatycznie)"),
                                _field("data_stala", "Data umowy", "DATEPICKER", default_value="2026-01-31")])
    got = {f["techName"]: f for *_, f in fields(generate(t, SHA)[0])}
    assert "defaultValue" not in got["data_wniosku"] and not got["data_wniosku"]["readOnly"]
    assert got["data_stala"]["defaultValue"] == "2026-01-31"
    form = generate(t, SHA)[0]
    next(f for *_, f in fields(form) if f["techName"] == "data_stala")["defaultValue"] = "dziś"
    assert "date" in {e["rule"] for e in validate(form)}


def test_consent_section_title():
    from coi.generator.build import consent_title
    page = lambda *texts: {"sections": [{"title": "Zgoda", "fields": [{"type": "CONSENT_SECTION", "consents": [{"html": f"<p>{x}</p>"} for x in texts]}]}]}
    for texts, title in ((["Wyrażam zgodę"], "Zgoda"), (["Oświadczam, że"], "Oświadczenie"), (["Wyrażam zgodę", "Oświadczam"], "Zgody i oświadczenia")):
        p = page(*texts)
        consent_title(p)
        assert p["sections"][0]["title"] == title
    one_doc = tree("form3", consents=[{"text": "Oświadczam, że dane są prawdziwe.", "src": []}])
    assert "Zgody i oświadczenia" in {s["title"] for _, s, _ in fields(generate(one_doc, SHA)[0])}


def test_show_if_always_emitted():
    t = _with_section("form3", [_field("czy_inny", "Czy adres do korespondencji jest inny", "RADIO", options=["Tak", "Nie"]),
                                _field("adres_kor", "Adres do korespondencji", preset="address", show_if={"field": "czy_inny", "options": ["Tak"]}),
                                _field("tytul", "Tytuł", show_if={"field": "czy_inny", "options": ["Może"], "negate": True})])
    form, rep, _ = generate(t, SHA)
    block = [f for *_, f in fields(form) if f["techName"].endswith("adres_kor") or "adres_kor_" in f["techName"]]
    assert len(block) == 9 and all(any("'czy_inny' in field.techName" in s["query"] for s in f["states"]) for f in block)
    assert any("zawsze spełniony" in w for w in rep["warnings"])  # a condition that cannot hide anything is reported, not lost silently


def test_multiple_files_sit_under_the_last_required_upload():
    t = _with_section("form3", [_field("odpis", "Odpis z rejestru", "FILE_UPLOADER"), _field("uwagi", "Uwagi", "TEXTAREA"),
                                _field("inne", "Inne załączniki", "FILE_UPLOADER", multiple=True, optional_evidence="...."),
                                _field("zgoda_wlasciciela", "Zgoda właściciela", "FILE_UPLOADER")])
    form, rep, _ = generate(t, SHA)
    page = next(t for t in form["tabs"] if any(q["field"]["title"] == "Dodatkowe" for q in t["questions"]))
    order = [(q["field"]["type"], q["field"]["title"], [c["field"]["techName"] for c in q["field"]["repeatingSectionGrid"]])
             for q in page["questions"]][-2:]
    assert order == [("SECTION", "Dodatkowe", ["odpis", "uwagi", "zgoda_wlasciciela"]), ("REPEATING_SECTION", "Inne załączniki", ["inne"])]
    (child,) = page["questions"][-1]["field"]["repeatingSectionGrid"]
    assert child["field"]["type"] == "FILE_UPLOADER" and child["field"]["validation"] == [] and rep["validation"] == []
    t2 = _with_section("form3", [_field("odpis", "Odpis z rejestru", "FILE_UPLOADER"),
                                 _field("inne", "Inne załączniki", "FILE_UPLOADER", multiple=True, optional_evidence="...."),
                                 _field("uwagi", "Uwagi", "TEXTAREA", optional_evidence="opcjonalnie")])
    titles = [(q["field"]["type"], q["field"]["title"]) for t in generate(t2, SHA)[0]["tabs"] for q in t["questions"]][-7:-4]
    assert titles == [("SECTION", "Dodatkowe"), ("REPEATING_SECTION", "Inne załączniki"), ("SECTION", "Dodatkowe")]
