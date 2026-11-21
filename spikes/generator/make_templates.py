"""Spike: build data templates (templates/*.json) and regression inputs (inputs/*.json) from patterns #1 and #5.

One-off: templates are meant to be edited by hand afterwards; this script only documents where they came from.
"""
import json
import pathlib
import sys

from coi_to_tree import tab_to_page

HERE = pathlib.Path(__file__).parent
MAT = pathlib.Path(__file__).resolve().parents[3] / "materials"
p1 = json.load(open(next(MAT.glob("1.*/konfiguracja*.json"))))
p5 = json.load(open(next(MAT.glob("5.*/konfiguracja*.json"))))
t1 = [tab_to_page(t) for t in p1["tabs"]]
t5 = [tab_to_page(t) for t in p5["tabs"]]

# R6: template fields are required unless listed here (standard: contact optional, KRS/REGON/flat number optional)
OPTIONAL = {"numer_lokalu", "numer_lokalu_siedziba", "numer_lokalu_inna_osoba", "regon", "numer_krs",
            "numer_telefonu", "adres_e_mail", "ulica", "ulica_siedziba", "ulica_inna_osoba",
            "ulica_zagranica", "ulica_siedziba_zagranica", "ulica_inna_osoba_zagranica"}
VALIDATORS = {"nip": ["NIP"], "regon": ["REGON"], "numer_pesel": ["PESEL"], "adres_e_mail": ["EMAIL"],
              "kod_pocztowy": ["ZIP_CODE"], "kod_pocztowy_siedziba": ["ZIP_CODE"], "kod_pocztowy_inna_osoba": ["ZIP_CODE"]}
APPLICANT_OPTIONS = {"Swoim": ["PERSON", "ANY"], "Innej osoby": ["PERSON", "ANY"],
                     "Osoby prawnej lub jednostki organizacyjnej": ["ANY", "ENTITY"]}


def annotate(page):
    for sec in page["sections"]:
        for f in sec["fields"]:
            if f["key"] in OPTIONAL:
                f["required"] = False
            if f["key"] in VALIDATORS:
                f["validators"] = VALIDATORS[f["key"]]
            # #5: only identity switches to PESEL; the address keeps MLPZ (PESEL has no postCode/street)
            if sec["key"] == "twoje_dane" and isinstance(f.get("default"), str) and f["default"].startswith("MLPZ."):
                f["default"] = "{{prefill}}." + f["default"][5:]
            if f["key"] == "wybierz_w_czyim_imieniu_wnioskujesz":
                f["options"] = [{"name": o, "when": {"applicant": APPLICANT_OPTIONS[o]}} for o in f["options"]]
    return page


dane = annotate(t1[0])
organ, urzad = dane["sections"][0], t5[0]["sections"][0]
organ["when"], urzad["when"] = {"addressee": ["ORGAN"]}, {"addressee": ["URZAD"]}
for s in (organ, urzad):
    s["fields"][0]["default"] = "{{addressee.name}}"
dane["sections"].insert(1, urzad)
pesel = next(f for f in t5[0]["sections"][2]["fields"] if f["key"] == "numer_pesel")
pesel |= {"when": {"prefill": ["PESEL"]}, "default": "PESEL.pesel", "validators": ["PESEL"]}
dane["sections"][3]["fields"].append(pesel)  # twoje_dane

kontakt = annotate(t5[2])  # "Kontakt i zgody" (#1 calls it "Kontakt z urzędem")
finish = t1[3]

(HERE / "templates").mkdir(exist_ok=True)
(HERE / "inputs").mkdir(exist_ok=True)
for name, page in (("dane", dane), ("kontakt", kontakt), ("finish", finish)):
    json.dump(page, open(HERE / "templates" / f"{name}.json", "w"), ensure_ascii=False, indent=1)

meta = {"p1": {"title": p1["title"], "addressee": {"kind": "ORGAN", "name": "Wójt Gminy Elbląg"}, "applicant": "ANY", "prefill": "MLPZ", "pages": t1[1:2]},
        "p5": {"title": p5["title"], "addressee": {"kind": "URZAD", "name": "Urząd Gminy Ulan-Majorat"}, "applicant": "ANY", "prefill": "PESEL", "pages": t5[1:2]}}
for name, inp in meta.items():
    for p in inp["pages"]:
        p.pop("type")
    json.dump(inp, open(HERE / "inputs" / f"{name}.json", "w"), ensure_ascii=False, indent=1)
print("ok", file=sys.stderr)
