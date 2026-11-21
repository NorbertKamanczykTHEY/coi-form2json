import json
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy import select

from coi import create_app
from coi.dictionaries import DictMatch, canonical, match
from coi.dictionaries.models import Item
from coi.make_token import make

SECRET = "test-secret-at-least-32-bytes-long!!"
H = {"Authorization": f"Bearer {make(SECRET, 'tester')}"}
CASES = json.loads((Path(__file__).parent / "match_cases.json").read_text())["cases"]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("JWT_SECRET", SECRET)
    mp.setenv("JWT_ALG", "HS256")
    mp.setenv("DATABASE_URL", f"sqlite:///{tmp_path_factory.mktemp('db')}/coi.sqlite")
    for k in ("JWT_ISSUER", "JWT_AUDIENCE"):
        mp.delenv(k, raising=False)
    yield create_app()  # seeds once for the module (~2 s)
    mp.undo()


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


def ids(app, did: str, level: int | None = None) -> list[str]:
    with app.config["STORE"].session() as s:
        q = select(Item.id).where(Item.dictionary_id == did)
        return list(s.scalars(q.where(Item.level == level) if level else q))


# Seed vs GUS / MSWiA, state on 2026-01-01: 16 voivodeships, 314 powiats + 66 cities with powiat rights, 2479 gminas (302/724/1453)
def test_teryt_counts_match_gus(app):
    assert len(ids(app, "WOJEWODZTWO")) == 16
    powiaty = ids(app, "POWIAT")
    assert len(powiaty) == 380
    assert sum(p[2:] >= "61" for p in powiaty) == 66  # TERC: city-powiat codes start at 61
    gminy = ids(app, "GMINA")
    assert Counter(g[-1] for g in gminy) == {"1": 302, "2": 1453, "3": 724}
    assert sorted(ids(app, "TERYT_4G_DOWODOWY", 3)) == sorted(gminy)
    assert len(ids(app, "MIEJSCOWOSC")) == len(ids(app, "TERYT_4G_DOWODOWY", 4)) > 50_000
    assert not ids(app, "TERYT_4G_DOWODOWY", 5)


def test_catalog_and_other_seeds(client):
    r = client.get("/api/v1/dictionaries", headers=H)
    cat = {d["id"]: d for d in r.json["items"]}
    assert {"Kraje", "TERYT_4G_DOWODOWY", "NUMERY_KIERUNKOWE", "DYSCYPLINY_SPORTOWE", "RASY_PSOW_AGRESYWNYCH"} <= set(cat)
    assert cat["Kraje"]["protected"] and cat["Kraje"]["items"] == 250
    assert cat["RASY_PSOW_AGRESYWNYCH"]["origin"] == "catalog" and cat["RASY_PSOW_AGRESYWNYCH"]["items"] == 11
    pl = client.get("/api/v1/dictionaries/NUMERY_KIERUNKOWE?q=polska", headers=H).json["items"]
    assert pl[0]["value"] == "+48" and pl[0]["id"] == "PL"
    assert client.get("/api/v1/dictionaries/Kraje?q=niemcy", headers=H).json["items"][0]["id"] == "DE"


def test_teryt_tree_search_and_paging(client):
    top = client.get("/api/v1/dictionaries/TERYT_4G_DOWODOWY", headers=H).json
    assert top["total"] == 16 and [i["name"] for i in top["items"][:5]] == ["dolnośląskie", "kujawsko-pomorskie", "lubelskie", "lubuskie", "łódzkie"]
    lodzkie = client.get("/api/v1/dictionaries/TERYT_4G_DOWODOWY?parent=10&limit=10&offset=20", headers=H).json
    assert lodzkie["total"] == 24 and len(lodzkie["items"]) == 4 and all(i["parent"] == "10" for i in lodzkie["items"])
    hit = client.get("/api/v1/dictionaries/TERYT_4G_DOWODOWY?q=ZGIERZ", headers=H).json["items"][0]
    assert hit["name"] == "Zgierz" and hit["level"] == 4 and hit["path"] == ["łódzkie", "zgierski", "Zgierz (gmina miejska)"]
    assert client.get("/api/v1/dictionaries/TERYT_4G_DOWODOWY?q=lodz", headers=H).json["items"][0]["name"] == "Łódź"  # no diacritics needed
    assert client.get("/api/v1/dictionaries/TERYT_4G_DOWODOWY?limit=501", headers=H).status_code == 400
    assert client.get("/api/v1/dictionaries/NIE_MA", headers=H).status_code == 404


def test_teryt_dowodowy_is_an_alias(client):
    assert canonical("TERYT_DOWODOWY") == "TERYT_4G_DOWODOWY" and canonical("Kraje") == "Kraje"
    assert "TERYT_DOWODOWY" not in {d["id"] for d in client.get("/api/v1/dictionaries", headers=H).json["items"]}
    r = client.get("/api/v1/dictionaries/TERYT_DOWODOWY", headers=H).json
    assert r["dictionary"]["id"] == "TERYT_4G_DOWODOWY" and r["total"] == 16
    assert client.post("/api/v1/dictionaries", json={"id": "TERYT_DOWODOWY", "name": "x"}, headers=H).status_code == 409


def test_match_public_api(app):
    """Contract the generator relies on (app/docs/design/generator.md, section 5)."""
    with app.config["STORE"].session() as s:
        m = match(s, "Kraj", "Kraj zamieszkania", "TEXT_FIELD", [])
        assert match(s, "PESEL", "", "TEXT_FIELD", []) is None
        adr = match(s, "Adres zamieszkania", type="SELECT")
    assert isinstance(m, DictMatch) and set(m.to_dict()) == {"dictionaryName", "decision", "score", "reason", "component",
                                                            "multiLevelTree", "searchEnabled", "proposal"}
    assert (m.dictionaryName, m.decision, m.component, m.proposal) == ("Kraje", "existing", "SELECT", None) and m.score == 1.0
    assert adr.dictionaryName == "TERYT_4G_DOWODOWY" and adr.multiLevelTree and adr.searchEnabled


def test_crud_needs_jwt(client):
    assert client.get("/api/v1/dictionaries").status_code == 401
    assert client.post("/api/v1/dictionaries", json={"id": "X", "name": "x"}).status_code == 401
    assert client.post("/api/v1/dictionaries/match", json={"label": "Kraj"}).status_code == 401


def test_crud(client):
    new = {"id": "RODZAJE_IMPREZ", "name": "Rodzaje imprez", "aliases": ["cel wynajęcia"], "levels": ["rodzaj", "impreza"],
           "items": [{"id": "r", "name": "rodzinne"}, {"id": "w", "name": "wesele", "parent": "r"}]}
    r = client.post("/api/v1/dictionaries", json=new, headers=H)
    assert r.status_code == 201 and r.json["created_by"] == "tester" and not r.json["protected"]
    assert client.post("/api/v1/dictionaries", json=new, headers=H).status_code == 409
    assert client.post("/api/v1/dictionaries", json={"id": "bad id", "name": "x"}, headers=H).status_code == 400
    bad_parent = new | {"id": "ZLE", "items": [{"id": "a", "name": "a", "parent": "nie-ma"}]}
    assert client.post("/api/v1/dictionaries", json=bad_parent, headers=H).status_code == 409

    base = "/api/v1/dictionaries/RODZAJE_IMPREZ"
    assert client.post(f"{base}/items", json={"id": "u", "name": "urodziny", "parent": "r"}, headers=H).json["level"] == 2
    assert client.post(f"{base}/items", json={"id": "u", "name": "dup"}, headers=H).status_code == 409
    assert client.put(f"{base}/items/u", json={"name": "urodziny dziecka"}, headers=H).json["name"] == "urodziny dziecka"
    assert client.put(f"{base}/items/nie-ma", json={"name": "x"}, headers=H).status_code == 404
    assert client.delete(f"{base}/items/r", headers=H).status_code == 409  # has children
    assert client.delete(f"{base}/items/u", headers=H).status_code == 204
    assert [i["name"] for i in client.get(f"{base}?parent=r", headers=H).json["items"]] == ["wesele"]

    assert client.put(base, json={"name": "Imprezy", "items": [{"id": "1", "name": "zebranie"}]}, headers=H).json["updated_by"] == "tester"
    assert client.get(base, headers=H).json["total"] == 1
    assert client.delete(base, headers=H).status_code == 204
    assert client.get(base, headers=H).status_code == 404

    r = client.delete("/api/v1/dictionaries/Kraje", headers=H)
    assert r.status_code == 409 and r.json["code"] == "protected_dictionary" and r.headers["Content-Type"] == "application/problem+json"


def test_match_endpoint_and_proposals(client):
    m = client.post("/api/v1/dictionaries/match", json={"label": "Kraj urodzenia", "type": "TEXT_FIELD"}, headers=H).json["match"]
    assert m["dictionaryName"] == "Kraje" and m["decision"] == "existing" and m["component"] == "SELECT" and m["proposal"] is None
    assert client.post("/api/v1/dictionaries/match", json={"label": "PESEL"}, headers=H).json["match"] is None

    rasa = client.post("/api/v1/dictionaries/match", json={"label": "Rasa psa", "type": "TEXT_FIELD"}, headers=H).json["match"]
    assert rasa["decision"] == "new" and len(rasa["proposal"]["items"]) == 11
    assert client.post("/api/v1/dictionaries/from-proposal", json=rasa["proposal"], headers=H).status_code == 201  # promotes the catalog entry
    again = client.post("/api/v1/dictionaries/match", json={"label": "Rasa psa", "type": "TEXT_FIELD"}, headers=H).json["match"]
    assert again["decision"] == "existing"

    opts = ["fortepian", "skrzypce", "wiolonczela", "flet", "klarnet", "trąbka", "perkusja", "gitara", "akordeon"]
    inst = client.post("/api/v1/dictionaries/match", json={"label": "Rodzaj instrumentu", "type": "CHECKBOX", "options": opts}, headers=H).json["match"]
    assert inst["decision"] == "new" and inst["proposal"]["id"] == "RODZAJ_INSTRUMENTU" and inst["proposal"]["source"] == "document"
    assert client.post("/api/v1/dictionaries/from-proposal", json=inst["proposal"], headers=H).status_code == 201
    assert client.post("/api/v1/dictionaries/from-proposal", json=inst["proposal"], headers=H).status_code == 409
    assert client.post("/api/v1/dictionaries/from-proposal", json={"id": "PUSTY", "name": "x", "items": []}, headers=H).status_code == 409
    seen = client.post("/api/v1/dictionaries/match", json={"label": "Instrument", "type": "CHECKBOX", "options": opts[:4]}, headers=H).json["match"]
    assert seen["dictionaryName"] == "RODZAJ_INSTRUMENTU" and seen["decision"] == "existing"  # options covered by the new dictionary


def test_tree_proposal_shape(client):
    m = client.post("/api/v1/dictionaries/match", json={"label": "Dyscypliny sportowe", "type": "CHECKBOX"}, headers=H).json["match"]
    assert m["multiLevelTree"] and m["searchEnabled"] and m["component"] == "CHECKBOX"
    kinds = m["proposal"]["items"]
    assert [k["name"] for k in kinds] == ["zespołowa", "indywidualna – inna", "indywidualna – lekkoatletyka"]
    assert sum(len(k["children"]) for k in kinds) == 20


@pytest.mark.parametrize("case", CASES, ids=[f"#{c['form']} {c['label'][:40]}" for c in CASES])
def test_match_forms_1_to_9(app, case):
    """Field -> result -> expected for forms #1-#9 (table in app/docs/dictionaries.md)."""
    with app.config["STORE"].session() as s:
        m = match(s, case["label"], "", case["type"], case.get("options", []))
    assert (m.dictionaryName if m else None) in case["accept"], m and m.reason
