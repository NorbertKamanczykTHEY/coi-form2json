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
           r"/wojewodztwo\w*/title: 'TERYT_(4G_)?DOWODOWY' -> 'Miejscowość'$",  # human title instead of the dictionary name
           r"^\+ /Dane/q/dane_innej_osoby/children/numer_pesel_inna_osoba$",  # Q33: Standardy s.15 over the patterns
           r"/title: 'Opłata skarbowa za pełnomonictwo' -> 'Opłata skarbowa za pełnomocnictwo'$"]  # the patterns' typo, fixed
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


def test_entity_only_applicant_has_no_choice_of_whose_name():
    # ADR 0026 (Q20/Q31 withdrawn): "tylko podmiot" -> entity data always shown, "jako kto" required without SHOW
    t = tree("form1", applicant_kinds=["legal_entity"], entity_option="Stowarzyszenie")
    form, rep, _ = generate(t, SHA)
    got = {f["techName"]: (s, f) for _, s, f in fields(form)}
    assert "wybierz_w_czyim_imieniu_wnioskujesz" not in got and "dane_innej_osoby" not in {s["techName"] for s, _ in got.values()}
    for k in ("nazwa", "kraj_siedziba"):
        assert got[k][0]["states"] == []  # section always visible
    role = got["wybierz_jako_kto_wnioskujesz"][1]
    assert role["states"] == [] and role["validation"] == ["REQUIRED"]
    rep_q = got["plik_z_odpisem_danych"][0]["states"][0]["query"]
    assert '"Reprezentant" in' in rep_q and "w_czyim_imieniu" not in rep_q
    assert got["regon"][1]["validation"] == ["REQUIRED", "REGON"]  # Standardy s.17
    assert rep["validation"] == []


def test_single_option_choice_disappears():
    t = _with_section("form3", [_field("jedyna", "Wybierz", "RADIO", options=["Tak"]),
                                _field("zalezne", "Szczegóły", show_if={"field": "jedyna", "options": ["Tak"]})])
    got = {f["techName"]: f for *_, f in fields(generate(t, SHA)[0])}
    assert "jedyna" not in got and got["zalezne"]["states"] == []


@pytest.mark.parametrize("signal", [False, True])
def test_registry_extract_always_required_with_signal(signal):
    t = tree("form1", applicant_kinds=["legal_entity"], entity_extract_required=signal, entity_extract_src=["p1.b31"] if signal else [])
    sec = next(s for _, s, f in fields(generate(t, SHA)[0]) if f["techName"] == "plik_z_odpisem_danych")
    assert (sec["states"] == []) is signal  # with the signal: every entity applicant, proxy included
    anyone = next(s for _, s, f in fields(generate(tree("form1"), SHA)[0]) if f["techName"] == "plik_z_odpisem_danych")
    assert anyone["title"] == "Potwierdzenie, że jesteś reprezentantem" and '"Reprezentant" in' in anyone["states"][0]["query"]


def test_proxy_id_card_when_the_paper_asks():
    blocks = {"p1.b7": "Dane pełnomocnika: imię, nazwisko, seria i numer dowodu osobistego"}
    asked = tree("form1", dropped=[{"reason": "proxy_data", "src": ["p1.b7"]}])
    f = next((f for *_, f in fields(generate(asked, SHA, blocks=blocks)[0]) if f["techName"].startswith("seria_i_numer_dowodu")), None)
    assert f and f["validation"] == ["REQUIRED", "SERIAL_NUMBER_ID_CARD"] and not f["readOnly"]  # no registry holds it (Dane inicjalne)
    assert not any(f["techName"].startswith("seria_i_numer_dowodu") for *_, f in fields(generate(tree("form1"), SHA, blocks=blocks)[0]))


def test_addressee_missing_and_consent_from_document():
    t = tree("form3", addressee=None, consents=[{"text": "Oświadczam, że dane są prawdziwe.", "src": ["p1.b9"]}])
    form, rep, _ = generate(t, SHA)
    urzad = next(f for *_, f in fields(form) if f["techName"] == "nazwa_urzedu")
    assert {"key": "nazwa_urzedu", "field_id": urzad["id"], "why": "brak adresata, pole nazwy urzędu do uzupełnienia"} in rep["needs_review"]
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
    page2 = next(t for t in generate(t2, SHA)[0]["tabs"] if any(q["field"]["title"] == "Dodatkowe" for q in t["questions"]))
    titles = [(q["field"]["type"], q["field"]["title"]) for q in page2["questions"]][-3:]
    assert titles == [("SECTION", "Dodatkowe"), ("REPEATING_SECTION", "Inne załączniki"), ("SECTION", "Dodatkowe")]


def test_fully_conditional_pages_merge_into_the_subject_page():
    # #9 (ADR 0020): spike tree of the real form; variant pages carry SHOW on every section, as extraction is asked to emit
    form, rep, _ = generate(tree("form9"), SHA)
    titles = [t["title"] for t in form["tabs"]]
    assert "Dane sportowca" not in titles and "Dane trenera i podopiecznych" not in titles
    assert titles[-2:] == ["Kontakt i zgody", "Strona końcowa"]
    host = next(t for t in form["tabs"] if t["title"] == "Dane wnioskodawcy - Klub sportowy")
    secs = [q["field"]["title"] for q in host["questions"]]
    assert secs[-6:] == ["Dane osobowe sportowca", "Dyscypliny sportowe", "Osiągnięcia sportowe",
                         "Dane osobowe trenera", "Dane podopiecznych trenera", "Załączniki dla podopiecznych"]
    assert all(q["field"]["states"] for q in host["questions"][-6:])  # SHOW kept on every moved section
    assert [q["y"] for q in host["questions"]] == sorted(q["y"] for q in host["questions"])
    assert rep["validation"] == []  # JSONata now points at the page the fields moved to (R6)
    assert sum("cała treść warunkowa" in w for w in rep["warnings"]) == 2


def test_conditional_pages_with_no_unconditional_page_share_one():
    t = json.loads((FIX / "form3.tree.json").read_text())
    radio = _field("rodzaj", "Rodzaj", "RADIO", options=["A", "B"])
    t["pages"] = [{"title": "Wybór", "sections": [{"title": "Wybór", "fields": [radio], "src": [],
                                                    "show_if": {"field": "rodzaj", "options": ["A", "B"]}}]},
                  {"title": "Wariant B", "sections": [{"title": "B", "fields": [_field("b", "Pole B")], "src": [],
                                                        "show_if": {"field": "rodzaj", "options": ["B"]}}]}]
    form, rep, _ = generate(FieldTree.model_validate(t), SHA)
    assert [t["title"] for t in form["tabs"]] == ["Dane", "Szczegóły wniosku", "Kontakt i zgody", "Strona końcowa"]
    assert [q["field"]["title"] for q in form["tabs"][1]["questions"]] == ["Wybór", "B"] and rep["validation"] == []


def test_identity_document_instead_of_pesel_only_for_persons_typed_in_paper_8():
    # G14: the logged-in applicant has a PESEL from the registry; the no-PESEL branch is for "Inna osoba" only
    from coi.extraction.anchors import blocks_of
    from coi.parsing import parse
    f = next(p for p in next(MATERIALS.glob("8. *")).glob("*.pdf"))
    form, rep, _ = generate(tree("pattern1"), SHA, blocks=blocks_of(parse(f.read_bytes(), f.name)))
    sec = next(q["field"] for q in form["tabs"][0]["questions"] if q["field"]["techName"] == "twoje_dane")
    own = {c["field"]["techName"] for c in sec["repeatingSectionGrid"]}
    assert not own & {"czy_masz_numer_pesel", "rodzaj_dokumentu_tozsamosci", "numer_dokumentu_tozsamosci"}
    got = {x["techName"]: x for *_, x in fields(form)}
    assert got["numer_pesel_inna_osoba"]["states"][0]["query"].startswith('$not("Nie" in')
    for k in ("rodzaj_dokumentu_tozsamosci_inna_osoba", "numer_dokumentu_tozsamosci_inna_osoba"):
        assert got[k]["validation"] == ["REQUIRED"] and got[k]["states"][0]["query"].startswith('("Nie" in')
    assert rep["validation"] == []
    plain = {f["techName"] for *_, f in fields(generate(tree("pattern1"), SHA, blocks={"p1.b1": "PESEL"})[0])}
    assert "numer_pesel" in plain and "czy_inna_osoba_ma_numer_pesel" not in plain  # no such sentence: nothing changes


def _blocks8():
    from coi.extraction.anchors import blocks_of
    from coi.parsing import parse
    f = next(p for p in next(MATERIALS.glob("8. *")).glob("*.pdf"))
    return blocks_of(parse(f.read_bytes(), f.name))


def test_applicant_address_section_is_left_to_the_template():
    # Section.party = the applicant's own address: the template "Dane" asks for it, a correspondence address turns on its block
    t = json.loads((FIX / "pattern1.tree.json").read_text())
    t["pages"].append({"title": "Dane składającego", "sections": [
        {"title": "Adres do korespondencji", "party": True, "src": [],
         "fields": [_field("ulica_kor", "Ulica"), _field("nr_domu_kor", "Numer domu")]},
        {"title": "Uwagi", "src": [], "fields": [_field("uwagi_s", "Uwagi", "TEXTAREA")]}]})
    form, rep, _ = generate(FieldTree.model_validate(t), SHA, blocks={"p1.b1": "Adres zamieszkania"})
    every = {f["techName"] for *_, f in fields(form)}
    assert "ulica_kor" not in every and "uwagi_s" in every and "czy_adres_do_korespondencji_jest_inny" in every
    assert any("adres wnioskodawcy jest w szablonie" in w for w in rep["warnings"]) and rep["validation"] == []


def test_no_correspondence_block_without_the_wording():
    techs = {f["techName"] for *_, f in fields(generate(tree("pattern1"), SHA, blocks={"p1.b1": "Adres zamieszkania"})[0])}
    assert "czy_adres_do_korespondencji_jest_inny" not in techs and "czy_inna_osoba_ma_numer_pesel" not in techs


def test_consent_condition_keeps_its_valid_part_paper_9():
    # EVAL-3 N1: the model pointed consents at a missing "pełnoletni" field; only that part goes, the variant part stays
    t = json.loads((FIX / "form9.tree.json").read_text())
    stypendium = t["pages"][0]["sections"][0]["fields"][0]["options"][0]
    t["consents"] = [{"text": "Oświadczam, że zapoznałem się z regulaminem stypendium.", "src": [],
                      "show_if": [{"field": "application_type", "options": [stypendium]},
                                  {"field": "czy_kandydat_jest_pelnoletni", "options": ["Tak"]}]}]
    form, rep, _ = generate(FieldTree.model_validate(t), SHA)
    consent = next(f for *_, f in fields(form) if f["techName"].startswith("zgoda_warunkowa"))
    (state,) = consent["states"]
    assert "'application_type' in field.techName" in state["query"] and "pelnoletni" not in state["query"]
    entry = next(r for r in rep["needs_review"] if r["key"] == consent["techName"])
    assert entry["field_id"] == consent["id"] and "czy_kandydat_jest_pelnoletni" in entry["why"] and rep["validation"] == []


def test_needs_review_names_a_field_in_polish():
    t = tree("form3", consents=[{"text": "Oświadczam.", "show_if": [{"field": "brak", "options": ["X"]}], "src": []}])
    src = next(f for p in t.pages for s in p.sections for f in s.fields).src[0]
    extraction = [{"key": None, "where": "zgoda 1", "why": "warunek wyświetlania wskazuje nieistniejące pole albo opcję"},
                  {"key": None, "anchor": src, "why": "miejsce do wpisania bez pola"},
                  {"key": None, "why": "wynik niepewny: bramka jakości nie przeszła w żadnej rundzie"}]
    form, rep, _ = generate(t, SHA, extra_review=extraction)
    ids = {f["id"]: f["techName"] for *_, f in fields(form)}
    assert all(r["key"] and r["why"] for r in rep["needs_review"])
    first, second, third = rep["needs_review"][:3]
    assert first["key"].startswith("zgoda_warunkowa") and ids[first["field_id"]] == first["key"]
    assert ids[second["field_id"]] == second["key"] and third["key"] == "formularz"


@pytest.mark.parametrize("name", ["form3", "form1"])
def test_applicant_self_only_drops_proxy_parts(name):
    form, rep, _ = generate(tree(name), SHA, applicant_self_only=True)
    techs = {f["techName"] for *_, f in fields(form)} | {s["techName"] for _, s, _ in fields(form)}
    assert not techs & {"pelnomocnictwo", "oplata_skarbowa_pelnomocnictwo_1", "oplata_skarbowa_pelnomocnictwo_2", "dane_innej_osoby",
                        "wybierz_jako_kto_wnioskujesz"}
    if name == "form3":  # person only: Standardy s.9 "pomiń tę sekcję"
        assert "podmiot_wniosku" not in techs
    else:  # any: own name or an entity, the entity acting through its representative only
        radio = next(f for *_, f in fields(form) if f["techName"] == "wybierz_w_czyim_imieniu_wnioskujesz")
        assert [o["name"] for o in radio["options"]] == ["Swoim", "Osoby prawnej lub jednostki organizacyjnej"]
        assert "plik_z_odpisem_danych" in techs
    assert rep["applicant_self_only"] == {"value": True, "source": "edytor", "quote": None} and rep["validation"] == []
    default = generate(tree(name), SHA)[1]["applicant_self_only"]
    assert default == {"value": False, "source": "domyślnie", "quote": None}


# ---- EVAL-3 rules (brief 10), generic examples --------------------------------------------------------------------
def _techs(form):
    return {f["techName"]: f for *_, f in fields(form)}


def test_g5_entity_option_is_the_standards_text():
    form, rep, _ = generate(tree("form3", applicant_kinds=["person", "legal_entity"], entity_option="właściciel / najemca / inny podmiot"), SHA)
    opts = [o["name"] for o in _techs(form)["wybierz_w_czyim_imieniu_wnioskujesz"]["options"]]
    assert "Osoby prawnej lub jednostki organizacyjnej" in opts and not any("najemca" in o for o in opts)
    assert any("zastąpiona opcją ze Standardów" in w for w in rep["warnings"]) and rep["validation"] == []


def test_g9_required_single_checkbox_becomes_yes_no_and_keeps_conditions():
    t = _with_section("form3", [_field("kompostownik", "Nieruchomość ma kompostownik", "CHECKBOX", options=["Oświadczam"]),
                                _field("ulga", "Kwota ulgi", "NUMBER", show_if={"field": "kompostownik", "options": ["Oświadczam"]})])
    form, rep, _ = generate(t, SHA)
    f = _techs(form)
    assert f["kompostownik"]["type"] == "RADIO" and [o["name"] for o in f["kompostownik"]["options"]] == ["Tak", "Nie"]
    assert f["ulga"]["states"][0]["query"].startswith('("Tak" in') and rep["validation"] == []


def test_g10_condition_on_every_option_of_a_required_choice_is_dropped():
    t = _with_section("form3", [_field("rodzaj", "Rodzaj", "RADIO", options=["A", "B", "C"]),
                                _field("wspolne", "Wspólne", show_if={"field": "rodzaj", "options": ["A", "B", "C"]}),
                                _field("tylko_a", "Tylko A", show_if={"field": "rodzaj", "options": ["A"]})])
    f = _techs(generate(t, SHA)[0])
    assert f["wspolne"]["states"] == [] and f["tylko_a"]["states"]


def test_g10_section_conditioned_on_a_later_page_moves_after_its_controller():
    t = json.loads((FIX / "form3.tree.json").read_text())
    t["pages"].insert(0, {"title": "Wcześniej", "sections": [
        {"title": "Stała", "fields": [_field("stala", "Stała")], "src": []},
        {"title": "Zależna", "show_if": {"field": "rodzaj", "options": ["A"]}, "fields": [_field("zalezna", "Zależna")], "src": []}]})
    t["pages"].append({"title": "Później", "sections": [{"title": "Wybór", "fields": [_field("rodzaj", "Rodzaj", "RADIO", options=["A", "B"])], "src": []}]})
    form, rep, _ = generate(FieldTree.model_validate(t), SHA)
    later = next(tab for tab in form["tabs"] if tab["title"] == "Później")
    assert [q["field"]["title"] for q in later["questions"]] == ["Wybór", "Zależna"] and rep["validation"] == []


def test_g11_flat_number_in_subject_is_optional():
    t = _with_section("form3", [_field("ulica_n", "Ulica"), _field("lokal_n", "Numer lokalu")])
    f = _techs(generate(t, SHA)[0])
    assert f["ulica_n"]["validation"] == ["REQUIRED"] and f["lokal_n"]["validation"] == []


def test_g1_cut_condition_leaves_no_branch_required():
    t = _with_section("form3", [_field("rodzaj", "Rodzaj", "RADIO", options=["A", "B"])],
                      consents=[{"text": "Zgoda dorosłego.", "src": [], "show_if": [{"field": "rodzaj", "options": ["A"]}, {"field": "brak", "options": ["Tak"]}]},
                                {"text": "Zgoda rodzica.", "src": [], "show_if": [{"field": "rodzaj", "options": ["A"]}, {"field": "brak", "options": ["Nie"]}]}])
    form, rep, _ = generate(t, SHA)
    cs = [c for *_, f in fields(form) if f["techName"].startswith("zgoda_warunkowa") for c in f["consentSectionConfig"]["consents"]]
    assert len(cs) == 2 and not any(c["required"] for c in cs)


def test_g3_template_and_duplicate_uploaders_go():
    t = _with_section("form3", [_field("zal1", "Kopia umowy", "FILE_UPLOADER"), _field("zal2", "Kopia umowy", "FILE_UPLOADER"),
                                _field("upow", "Dokumenty upoważniające do złożenia wniosku", "FILE_UPLOADER")])
    f = _techs(generate(t, SHA)[0])
    assert "zal1" in f and "zal2" not in f and "upow" not in f


def test_g6_rate_goes_into_the_result_description_and_masks_go():
    t = _with_section("form3", [_field("stawka", "Stawka opłaty", "TEXT_BLOCK", default_value="38 zł"),
                                _field("oplata", "Wysokość opłaty", "NUMBER"),
                                _field("data", "Data wpłaty", "DATEPICKER", description="DD-MM-RRRR"),
                                _field("konto", "Numer rachunku", description="w formacie XXXXXXXXXXXXXXXXXXXXXXXXXX")])
    f = _techs(generate(t, SHA)[0])
    assert "stawka" not in f and "38 zł" in f["oplata"]["description"] and "defaultValue" not in f["oplata"]
    assert f["data"]["description"] == "" and "26 cyfr" in f["konto"]["description"]


def test_g8_case_fee_on_the_contact_page_with_proof():
    form, rep, _ = generate(tree("form3", case_fee="Opłata 17 zł na konto urzędu, płatna przed złożeniem wniosku.", case_fee_proof=True), SHA)
    tab = next(t for t in form["tabs"] if t["title"] == "Kontakt i zgody")
    sec = next(q["field"] for q in tab["questions"] if q["field"]["title"] == "Opłata")
    kinds = [c["field"]["type"] for c in sec["repeatingSectionGrid"]]
    assert kinds == ["TEXT_BLOCK", "FILE_UPLOADER"] and "17 zł" in sec["repeatingSectionGrid"][0]["field"]["description"]
    assert rep["validation"] == []
    assert "Opłata" not in [q["field"]["title"] for t in generate(tree("form3"), SHA)[0]["tabs"] for q in t["questions"]]


def test_g12_identical_variant_blocks_merge():
    t = json.loads((FIX / "form3.tree.json").read_text())
    blk = lambda k: [_field(f"imie_{k}", "Imię"), _field(f"uwagi_{k}", "Uwagi", "TEXTAREA")]
    t["pages"].append({"title": "Warianty", "sections": [
        {"title": "Wybór", "fields": [_field("wariant", "Wariant", "RADIO", options=["I", "II", "III"])], "src": []},
        {"title": "Dane I", "show_if": {"field": "wariant", "options": ["I"]}, "fields": blk("a"), "src": []},
        {"title": "Dane II", "show_if": {"field": "wariant", "options": ["II"]}, "fields": blk("b"), "src": []}]})
    t["consents"] = [{"text": "Oświadczam.", "src": [], "show_if": [{"field": "imie_b", "options": ["x"]}]}]
    form, rep, _ = generate(FieldTree.model_validate(t), SHA)
    f = _techs(form)
    assert "imie_a" in f and "imie_b" not in f and '"II" in' in next(
        q["field"] for tab in form["tabs"] for q in tab["questions"] if q["field"]["title"] == "Dane I")["states"][0]["query"]


def test_g15_long_single_choice_becomes_a_searchable_select_multiple_choice_stays():
    opts = [f"Opcja {i}" for i in range(16)]
    t = _with_section("form3", [_field("jedna", "Gmina", "RADIO", options=opts), _field("wiele", "Dyscypliny", "CHECKBOX", options=opts)])
    form, rep, _ = generate(t, SHA)
    f = _techs(form)
    assert f["jedna"]["type"] == "SELECT" and f["jedna"]["searchEnabled"] is True
    assert f["wiele"]["type"] == "CHECKBOX" and len(f["wiele"]["options"]) == 16
    assert not any("wyszukiwark" in w for w in rep["warnings"]) and rep["validation"] == []


def test_g16_subject_label_equal_to_a_template_label_takes_the_paper_wording():
    t = _with_section("form3", [{**_field("organ_wplaty", "Nazwa organu"), "source_label": "Nazwa organu, w którym zapłacono opłatę:"}])
    assert _techs(generate(t, SHA)[0])["organ_wplaty"]["title"] == "Nazwa organu, w którym zapłacono opłatę"


def test_consent_required_and_proxy_id_card_from_the_tree():
    t = tree("form3", consents=[{"text": "Zgadzam się na kontakt e-mailowy.", "required": False, "src": []}], proxy_id_card=True)
    form, rep, _ = generate(t, SHA)
    cs = [c for *_, f in fields(form) if f["type"] == "CONSENT_SECTION" for c in f["consentSectionConfig"]["consents"]]
    assert [c["required"] for c in cs] == [True, False]
    assert any("SERIAL_NUMBER_ID_CARD" in f["validation"] for *_, f in fields(form))


def test_g6_rate_goes_to_the_nearest_number_of_its_section():
    t = _with_section("form3", [_field("liczba", "Liczba gospodarstw", "NUMBER"), _field("uwagi_x", "Uwagi"),
                                _field("stawka_a", "Stawka", "TEXT_BLOCK", default_value="38 zł"), _field("opis_x", "Opis"),
                                _field("kwota", "Wysokość opłaty", "NUMBER"),
                                _field("zwolnienie", "Stawka zwolnienia", "TEXT_BLOCK", default_value="- 15 zł")])
    f = _techs(generate(t, SHA)[0])
    assert "stawka_a" not in f and "zwolnienie" not in f
    assert "38 zł" in f["kwota"]["description"] and "15 zł" in f["kwota"]["description"] and f["liczba"]["description"] == ""
    alone = _techs(generate(_with_section("form3", [_field("stawka_b", "Stawka", "TEXT_BLOCK", default_value="38 zł")]), SHA)[0])
    assert "38 zł" in alone["stawka_b"]["description"]  # no NUMBER in the section: the block stays


def _numbered(n, prefix, k):
    return [{**_field(f"{k}{i}", f"Pole {k}{i}"), "number": f"{prefix}.{i}"} for i in range(n)]


def test_g12_long_section_splits_where_the_paper_numbering_changes_group():
    t = json.loads((FIX / "form3.tree.json").read_text())
    t["pages"].append({"title": "Nieruchomość", "sections": [
        {"title": "Dane nieruchomości", "number": "D", "src": [], "fields": _numbered(6, "D.1", "a") + _numbered(6, "D.2", "b")}]})
    form, rep, _ = generate(FieldTree.model_validate(t), SHA)
    tab = next(x for x in form["tabs"] if x["title"] == "Nieruchomość")
    assert [len(q["field"]["repeatingSectionGrid"]) for q in tab["questions"]] == [6, 6] and rep["validation"] == []
    flat = json.loads((FIX / "form3.tree.json").read_text())
    flat["pages"].append({"title": "Bez", "sections": [{"title": "Długa", "src": [], "fields": [_field(f"c{i}", f"Pole {i}") for i in range(12)]}]})
    tab = next(x for x in generate(FieldTree.model_validate(flat), SHA)[0]["tabs"] if x["title"] == "Bez")
    assert len(tab["questions"]) == 1  # no numbering: no blind cut


def test_g12_long_page_splits_between_numbered_sections():
    t = json.loads((FIX / "form3.tree.json").read_text())
    secs = [{"title": f"Część {c}", "number": c, "src": [], "fields": _numbered(5, c, c.lower())} for c in "ABC"]
    t["pages"].append({"title": "Szczegóły", "sections": secs})
    form, rep, _ = generate(FieldTree.model_validate(t), SHA)
    titles = [x["title"] for x in form["tabs"]]
    assert "Szczegóły" in titles and "Część C" in titles and rep["validation"] == []
    unnumbered = json.loads((FIX / "form3.tree.json").read_text())
    unnumbered["pages"].append({"title": "Szczegóły", "sections": [{**x, "number": None} for x in secs]})
    assert "Część C" not in [x["title"] for x in generate(FieldTree.model_validate(unnumbered), SHA)[0]["tabs"]]


@pytest.mark.parametrize("source", ["26. Miejscowość:", "B.2 Miejscowość", "D.1.26) Miejscowość", "IV. Miejscowość", "(3) Miejscowość"])
def test_paper_numbering_never_reaches_a_label(source):
    # G16 takes the paper's wording on a clash with a template label ("Miejscowość"), but without the item number
    t = _with_section("form3", [{**_field("miejscowosc_n", "Miejscowość"), "source_label": source, "number": "26"},
                                _field("ulica_n", "12. Ulica")])
    f = _techs(generate(t, SHA)[0])
    assert f["miejscowosc_n"]["title"] == "Miejscowość" and f["ulica_n"]["title"] == "Ulica"
