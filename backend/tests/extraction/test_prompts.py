"""ADR 0024: prompts and the FieldTree schema carry no phrases taken from the competition forms; applicant signals are present."""
import json
import re

from coi.extraction.tree import FieldTree
from coi.prompts import prompt

FORM_PHRASES = re.compile(r"klub|sportow|trener|podopieczn|\bps(a|ów)\b|chart|gdyni|zgierz|elbląg|ulan|nadpłat|korekta deklaracji|książeczk|stypendi", re.I)


def texts():
    yield prompt("field_extraction", schema="", text="")
    yield prompt("field_extraction_skeleton", schema="", text="")
    yield prompt("field_extraction_page", skeleton="", page="", variant_rule="", schema="", text="")
    yield json.dumps(FieldTree.model_json_schema(), ensure_ascii=False)


def test_no_phrases_from_specific_forms():
    for t in texts():
        assert not FORM_PHRASES.search(t), FORM_PHRASES.search(t)[0]


def test_applicant_kind_signals_in_prompts():
    main, skel = list(texts())[:2]
    for t in (main, skel):
        assert "`person`" in t and "`legal_entity`" in t and "REGON" in t and "pełnomocnik" in t.lower()
