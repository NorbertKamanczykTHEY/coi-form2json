"""Build dictionary seed files once, offline: coi/dictionaries/seed/<ID>.json.gz + seed/sources.json.

    uv run python scripts/fetch_dictionaries.py            # downloads TERYT from GUS (cached in scripts/.cache)

Sources and licenses: app/docs/dictionaries.md. Runtime never calls the network; it only reads the seed files.
Item shape: {"id", "name", "parent"?, "level"} (level 1 = root). Order of items = display order.
"""
import gzip
import html
import io
import json
import re
import ssl
import sys
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

import certifi
import phonenumbers
from babel import Locale

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "coi" / "dictionaries" / "seed"
CACHE = Path(__file__).resolve().parent / ".cache"
ETERYT = "https://eteryt.stat.gov.pl/eTeryt/rejestr_teryt/udostepnianie_danych/baza_teryt/uzytkownicy_indywidualni/pobieranie/pliki_pelne.aspx"
UA = {"User-Agent": "coi-formularze-seed/1.0"}


def eteryt(target: str) -> tuple[str, bytes]:
    """The GUS page serves zips only through an ASP.NET postback, so replay it: GET the form, POST its hidden fields with __EVENTTARGET."""
    cached = sorted(CACHE.glob(f"{target}_*.zip"))
    if cached:
        return cached[-1].name, cached[-1].read_bytes()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())))
    page = opener.open(urllib.request.Request(ETERYT, headers=UA), timeout=60).read().decode()
    form = {m[1]: html.unescape(m[2]) for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page)}
    form |= {"__EVENTTARGET": f"ctl00$body$B{target}Pobierz", "__EVENTARGUMENT": ""}
    r = opener.open(urllib.request.Request(ETERYT, urllib.parse.urlencode(form).encode(), UA), timeout=300)
    name = re.search(r"filename=([^;]+)", r.headers["Content-Disposition"])[1].strip()
    data = r.read()
    assert data[:2] == b"PK", f"{target}: expected a zip, got {data[:60]!r}"
    CACHE.mkdir(exist_ok=True)
    (CACHE / name).write_bytes(data)
    return name, data


def rows(zipped: bytes) -> list[dict]:
    z = zipfile.ZipFile(io.BytesIO(zipped))
    xml = next(n for n in z.namelist() if n.lower().endswith(".xml"))
    return [{c.tag: (c.text or "").strip() for c in row} for row in ET.parse(z.open(xml)).getroot().iter("row")]


def teryt() -> dict[str, list[dict]]:
    terc_file, terc = eteryt("TERCUrzedowy")
    simc_file, simc = eteryt("SIMCUrzedowy")
    terc, simc = rows(terc), rows(simc)
    woj = {r["WOJ"]: r["NAZWA"].lower() for r in terc if not r["POW"]}
    pow_ = {r["WOJ"] + r["POW"]: r["NAZWA"] for r in terc if r["POW"] and not r["GMI"]}
    # Legal gminy only (rodzaj 1 miejska, 2 wiejska, 3 miejsko-wiejska). Units 4/5 (miasto / obszar wiejski of a 3)
    # and 8/9 (dzielnice Warszawy, delegatury) fold into their gmina, so one address has one path.
    gmi = {r["WOJ"] + r["POW"] + r["GMI"] + "_" + r["RODZ"]: f'{r["NAZWA"]} ({r["NAZWA_DOD"]})' for r in terc if r["RODZ"] in ("1", "2", "3")}

    def gmina_of(r: dict) -> str:
        if r["RODZ_GMI"] in ("8", "9"):  # a dzielnica/delegatura has its own GMI number; its gmina is the city, GMI 01 rodzaj 1
            return r["WOJ"] + r["POW"] + "01_1"
        return r["WOJ"] + r["POW"] + r["GMI"] + "_" + {"4": "3", "5": "3"}.get(r["RODZ_GMI"], r["RODZ_GMI"])

    towns = [r for r in simc if r["SYM"] == r["SYMPOD"]]
    parts = [r for r in simc if r["SYM"] != r["SYMPOD"]]
    town_ids = {r["SYM"] for r in towns}
    assert all(gmina_of(r) in gmi for r in towns), "SIMC locality without a TERC gmina"
    by_name = lambda xs: sorted(xs, key=lambda i: (i.get("parent") or "", coll(i["name"])))  # noqa: E731
    L1 = by_name({"id": k, "name": v, "level": 1} for k, v in woj.items())
    L2 = by_name({"id": k, "name": v, "parent": k[:2], "level": 2} for k, v in pow_.items())
    L3 = by_name({"id": k, "name": v, "parent": k[:4], "level": 3} for k, v in gmi.items())
    L4 = by_name({"id": r["SYM"], "name": r["NAZWA"], "parent": gmina_of(r), "level": 4} for r in towns)
    L5 = by_name({"id": r["SYM"], "name": r["NAZWA"], "parent": r["SYMPOD"], "level": 5} for r in parts if r["SYMPOD"] in town_ids)
    # Gmina ids are WOJPOWGMI_RODZ: plain 7-digit TERC codes collide with 7-digit SIMC ids in one tree
    assert not {i["id"] for i in L3} & {i["id"] for i in L4 + L5}, "TERC/SIMC id collision"
    flat = lambda xs: [{k: v for k, v in i.items() if k != "level"} | {"level": 1} for i in xs]  # noqa: E731
    SOURCES["TERYT"] = {"files": [terc_file, simc_file], "counts": {"województwa": len(L1), "powiaty": len(L2), "gminy": len(L3), "miejscowości": len(L4), "części miejscowości": len(L5)}}
    return {
        "TERYT_4G_DOWODOWY": L1 + L2 + L3 + L4,
        "WOJEWODZTWO": flat(L1), "POWIAT": flat(L2), "GMINA": flat(L3), "MIEJSCOWOSC": flat(L4),
    }


def coll(s: str) -> str:
    """Polish sort key without ICU: ą sorts after every a-word and before b, ł after l, and so on ("~" > any letter)."""
    out = []
    for c in s.casefold():
        d = unicodedata.normalize("NFD", c)
        out.append("l~" if c == "ł" else d[0] + "~" if d != c else c)
    return "".join(out)


# ISO 3166-1 alpha-2 from CLDR, minus CLDR's groupings and exceptionally reserved codes; XK (Kosowo) stays, Polish registries list it.
NOT_COUNTRIES = {"EU", "EZ", "UN", "QO", "XA", "XB", "ZZ", "AC", "CP", "DG", "EA", "IC", "TA", "CQ"}


def countries() -> list[tuple[str, str]]:
    pl = Locale("pl").territories
    return sorted(((c, pl[c]) for c in pl if len(c) == 2 and c.isalpha() and c not in NOT_COUNTRIES), key=lambda x: coll(x[1]))


def kraje() -> list[dict]:
    return [{"id": c, "name": n, "level": 1} for c, n in countries()]


def numery() -> list[dict]:
    out = []
    for c, n in countries():
        if code := phonenumbers.country_code_for_region(c):
            out.append({"id": c, "name": f"+{code} {n}", "value": f"+{code}", "level": 1})
    return out


def tree(spec: dict[str, list[str]]) -> list[dict]:
    items = []
    for i, (kind, children) in enumerate(spec.items(), 1):
        items.append({"id": str(i), "name": kind, "level": 1})
        items += [{"id": f"{i}.{j}", "name": c, "parent": str(i), "level": 2} for j, c in enumerate(children, 1)]
    return items


def simple(names: list[str]) -> list[dict]:
    return [{"id": str(i), "name": n, "level": 1} for i, n in enumerate(names, 1)]


# Lists from official texts, copied by hand (sources in app/docs/dictionaries.md)
RASY = ["amerykański pit bull terrier", "pies z Majorki (Perro de Presa Mallorquin)", "buldog amerykański", "dog argentyński",
        "pies kanaryjski (Perro de Presa Canario)", "tosa inu", "rottweiler", "akbash dog", "anatolian karabash",
        "moskiewski stróżujący", "owczarek kaukaski"]  # Dz.U. 2003 nr 77 poz. 687, § 1
# #9 lists 3 kinds and 20 disciplines without saying which kind each belongs to; the split below is ours
DYSCYPLINY = {
    "zespołowa": ["hokej", "koszykówka", "piłka nożna", "piłka ręczna", "piłka siatkowa", "piłka wodna", "unihokej"],
    "indywidualna – inna": ["gimnastyka artystyczna", "karate", "kolarstwo", "łucznictwo", "łyżwiarstwo", "narciarstwo klasyczne",
                            "sport motocyklowy", "sporty walki", "sporty wodne", "tenis stołowy", "tenis ziemny", "zapasy"],
    "indywidualna – lekkoatletyka": ["lekkoatletyka"],
}
DORECZENIA = ["Poczta tradycyjna", "Skrzynka ePUAP", "e-Doręczenia"]  # #9; e-Doręczenia: ustawa z 18.11.2020 o doręczeniach elektronicznych
PODATKI = ["podatek od nieruchomości", "podatek rolny", "podatek leśny", "podatek od środków transportowych",
           "opłata targowa", "opłata miejscowa", "opłata uzdrowiskowa", "opłata reklamowa", "opłata od posiadania psów",
           "łączne zobowiązanie pieniężne"]
SOURCES: dict = {}


def main() -> None:
    data = teryt() | {
        "Kraje": kraje(), "NUMERY_KIERUNKOWE": numery(),
        "RASY_PSOW_AGRESYWNYCH": simple(RASY), "DYSCYPLINY_SPORTOWE": tree(DYSCYPLINY),
        "SPOSOBY_DORECZENIA": simple(DORECZENIA), "RODZAJE_PODATKOW_LOKALNYCH": simple(PODATKI),
    }
    catalog = {d["id"] for d in json.loads((OUT.parent / "catalog.json").read_text())["dictionaries"]}
    assert catalog == set(data), f"catalog.json and seed differ: {catalog ^ set(data)}"
    OUT.mkdir(exist_ok=True)
    for did, items in data.items():
        assert len({i["id"] for i in items}) == len(items), f"{did}: duplicate item ids"
        raw = json.dumps(items, ensure_ascii=False, separators=(",", ":")).encode()
        (OUT / f"{did}.json.gz").write_bytes(gzip.compress(raw, 9, mtime=0))  # mtime=0: same data, same bytes
        print(f"{did:28} {len(items):7} items")
    SOURCES["built"] = date.today().isoformat()
    SOURCES["counts"] = {k: len(v) for k, v in data.items()}
    SOURCES["libraries"] = {"babel (CLDR)": __import__("babel").__version__,
                            "phonenumbers (libphonenumber)": phonenumbers.__version__}
    (OUT / "sources.json").write_text(json.dumps(SOURCES, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    sys.exit(main())
