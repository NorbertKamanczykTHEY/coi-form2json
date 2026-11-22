"""extract(): ladder, repair rounds, two-stage path. A fake provider replays canned replies; the `eden` test calls the real API."""
import json
from pathlib import Path

import pytest

from coi import llm
from coi.extraction import ExtractionError, extract
from coi.parsing.model import Block, Page, ParsedDocument

from .test_gate import BLOCKS, tree as good_tree


def doc(texts):
    return ParsedDocument(source={"filename": "t.docx"}, pages=[Page(1, [Block("paragraph", t) for t in texts])])


DOC = doc(list(BLOCKS.values()))


class Fake:
    name = "fake"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def chat(self, model, content, max_tokens, response_format=None):
        self.calls.append((model, content))
        r = self.replies.pop(0)
        return llm.Reply(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False), "stop", 0.001, 0.1)


@pytest.fixture(autouse=True)
def ladder(monkeypatch, request):
    if request.node.get_closest_marker("eden"):
        return  # the real run uses the configured ladder
    monkeypatch.setenv("EXTRACTION_LADDER", "small,large")
    monkeypatch.setenv("EXTRACTION_TWO_STAGE_BLOCKS", "150")


def good():
    return good_tree().model_dump(exclude_none=True)


def bad():  # G5: radio with one option
    t = good()
    t["pages"][0]["sections"][0]["fields"][0]["options"] = ["Przelew"]
    return t


def test_first_rung_accepted():
    p = Fake([good()])
    r = extract(DOC, provider=p)
    assert [m for m, _ in p.calls] == ["small"]
    assert r.cost == 0.001 and r.trace[0]["accepted"]
    assert {f.key for f in r.tree.pages[0].sections[0].fields} == {"wybierz_sposob", "numer_rachunku"}


def test_schema_repair_then_gate_repair_then_escalation():
    events = []
    p = Fake(["not json", bad(), bad(), good()])  # small: schema repair, gate reject, gate repair rejected; large ok
    r = extract(DOC, on_event=lambda e, d: events.append(d), provider=p)
    assert [m for m, _ in p.calls] == ["small", "small", "small", "large"]
    assert "POPRZEDNIA ODPOWIEDŹ MA BŁĘDY" in p.calls[1][1] and "G5" in p.calls[2][1]
    assert [(t["model"], t["round"], t["accepted"]) for t in r.trace] == [("small", "first", False), ("small", "repair", False), ("large", "first", True)]
    assert r.cost == 0.004 and events[-1]["accepted"]
    assert not any("wynik niepewny" in x["why"] for x in r.needs_review)


def test_nothing_passes_returns_best_with_needs_review():
    r = extract(DOC, provider=Fake([bad()] * 4))
    head = r.needs_review[0]
    assert head["why"].startswith("wynik niepewny") and any(f.startswith("G5") for f in head["fails"])
    assert all("key" in x for x in r.needs_review)
    assert any(x["key"] == "wybierz_sposob" and "2 opcje" in x["why"] for x in r.needs_review)


def test_no_valid_schema_raises():
    with pytest.raises(ExtractionError):
        extract(DOC, provider=Fake(["{}"] * 4))


def test_two_stage_for_multi_variant_document(monkeypatch):
    monkeypatch.setenv("EXTRACTION_WORKERS", "1")  # replies are consumed in order
    monkeypatch.setenv("EXTRACTION_PARALLEL_RUNGS", "0")
    d = doc(["Wniosek o stypendium", "Wynik sportowy ___", "Wniosek o nagrodę", "Wynik sportowy ___", "Klub ___",
             "Zgoda osoby niepełnoletniej: wyrażam zgodę", "Zgoda dla nagrody: akceptuję regulamin"])
    skel = {"title": "Wniosek o stypendium lub nagrodę", "applicant_kinds": ["person"], "variants": ["Stypendium", "Nagroda"],
            "dropped": [{"reason": "title", "src": ["p1.b0"]}, {"reason": "title", "src": ["p1.b2"]}, {"reason": "consent", "src": ["p1.b5-p1.b6"]}],
            "conditions": [{"key": "pelnoletni", "label": "Czy osoba jest pełnoletnia", "options": ["Tak", "Nie"]}],
            "consents": [{"text": "Wyrażam zgodę", "src": ["p1.b5"], "condition": {"field": "pelnoletni", "options": ["Nie"]}},
                         {"text": "Akceptuję regulamin", "src": ["p1.b6"], "variants": ["Nagroda"]},
                         {"text": "Zgoda wspólna", "src": ["p1.b6"], "variants": ["Stypendium", "Nagroda"]}],
            "pages": [{"title": "Osiągnięcia", "sections": [
                {"title": "Wyniki", "src": ["p1.b1", "p1.b3"], "variants": ["Stypendium", "Nagroda"]},
                {"title": "Klub", "src": ["p1.b4"], "variants": ["Nagroda"]}]}]}
    wyniki = {"title": "Osiągnięcia", "sections": [
        {"title": "Wyniki", "src": ["p1.b1", "p1.b3"], "fields": [{"key": "wynik", "label": "Wynik sportowy", "source_label": "Wynik sportowy", "type": "TEXTAREA", "src": ["p1.b1", "p1.b3"]}]}]}
    klub = {"title": "Osiągnięcia", "sections": [  # a per-section call may echo another section: only its own is kept
        {"title": "Klub", "src": ["p1.b4"], "fields": [{"key": "klub", "label": "Klub", "source_label": "Klub", "type": "TEXT_FIELD", "src": ["p1.b4"]}]},
        {"title": "Wyniki", "src": ["p1.b1"], "fields": [{"key": "x", "label": "X", "source_label": "Wynik sportowy", "type": "TEXT_FIELD", "src": ["p1.b1"]}]}]}
    p = Fake([skel, wyniki, klub])
    r = extract(d, provider=p)
    assert "PIERWSZY ETAP" in p.calls[0][1] and "DRUGI ETAP" in p.calls[1][1]
    assert "[p1.b0]" not in p.calls[1][1] and "[p1.b4]" not in p.calls[1][1]  # stage two: one call per section, only its blocks
    assert [f.key for f in r.tree.pages[0].sections[2].fields] == ["klub"]
    secs = r.tree.pages[0].sections
    assert [s.title for s in secs] == ["Rodzaj wniosku", "Wyniki", "Klub"]
    radio, adult = secs[0].fields
    assert adult.type == "RADIO" and adult.source_label.startswith("Zgoda osoby")  # grounded in the consent it controls
    c1, c2, c3 = r.tree.consents
    assert [(x.field, x.options) for x in c1.show_if] == [(adult.key, ["Nie"])]
    assert [(x.field, x.options) for x in c2.show_if] == [(radio.key, ["Nagroda"])]
    assert c3.show_if == []
    assert radio.type == "RADIO" and radio.options == ["Stypendium", "Nagroda"]
    assert secs[1].show_if is None  # common to all variants
    assert secs[2].show_if.field == radio.key and secs[2].show_if.options == ["Nagroda"]
    assert r.trace[-1]["accepted"] and r.trace[-1]["mode"] == "two_stage", r.trace


MATERIALS = Path(__file__).resolve().parents[4] / "materials"


@pytest.mark.eden
def test_real_form1_via_eden():
    from coi.parsing import parse

    path = next(MATERIALS.glob("1. */Wniosek o ustalenie numeru porządkowego nieruchomości.docx"))
    r = extract(parse(path.read_bytes(), path.name))
    fields = [f for p in r.tree.pages for s in p.sections for f in s.fields]
    print(f"\n#1: {len(fields)} fields, needs_review={len(r.needs_review)}, cost=${r.cost}, trace={[(t['model'], t['round'], t['accepted']) for t in r.trace]}")
    assert 3 <= len(fields) <= 10 and r.cost > 0


def test_repair_keeps_control_fields_that_show_if_still_names():
    first = bad()
    first["pages"][0]["sections"][0]["fields"].append({"key": "pelnoletni", "label": "Czy osoba jest pełnoletnia", "source_label": "Sposób",
                                                       "type": "RADIO", "options": ["Tak", "Nie"], "src": ["p1.b1"]})
    repaired = good()
    repaired["consents"] = [{"text": "Zgoda", "show_if": [{"field": "czy_osoba_jest_pelnoletnia", "options": ["Nie"]}]}]
    r = extract(DOC, provider=Fake([first, repaired]))
    keys = [f.key for p in r.tree.pages for s in p.sections for f in s.fields]
    assert "czy_osoba_jest_pelnoletnia" in keys and r.trace[-1]["accepted"], r.trace


def test_repair_that_drops_fields_is_rejected_and_best_keeps_coverage():
    first = bad()  # G5 only
    collapsed = good()
    collapsed["pages"][0]["sections"][0]["fields"] = collapsed["pages"][0]["sections"][0]["fields"][:0] + [
        {"key": "x", "label": "Wybierz sposób", "source_label": "Sposób", "type": "RADIO", "options": ["A"], "src": ["p1.b1"]}]
    r = extract(DOC, provider=Fake([first, collapsed, first, collapsed]))
    assert [t["round"] for t in r.trace] == ["first", "repair", "first", "repair"]
    assert "dropped fields" in r.trace[1]["error"]  # EVAL-5 T3: any loss of fields, not only a collapse
    assert len([f for p in r.tree.pages for s in p.sections for f in s.fields]) == 2  # the full first tree, not the collapsed one


def test_repair_skipped_past_the_time_budget(monkeypatch):
    monkeypatch.setenv("EXTRACTION_REPAIR_BUDGET_S", "0")
    p = Fake([bad(), good()])
    r = extract(DOC, provider=p)
    assert [m for m, _ in p.calls] == ["small", "large"]  # no repair call: straight to the next rung
    assert any("time budget" in (s.get("error") or "") for s in r.trace) and r.trace[-1]["accepted"]


class ByModel:  # thread-safe fake: the reply depends on the model and the stage, not on the call order
    name = "fake"

    def __init__(self, replies):
        self.replies, self.calls, self._lock = replies, [], __import__("threading").Lock()

    def chat(self, model, content, max_tokens, response_format=None):
        with self._lock:
            self.calls.append((model, content))
        r = self.replies[(model, "PIERWSZY ETAP" in content)]
        return llm.Reply(json.dumps(r, ensure_ascii=False), "stop", 0.001, 0.1)


def test_parallel_rungs_start_together_and_the_weaker_passing_rung_wins(monkeypatch):
    monkeypatch.setenv("EXTRACTION_TWO_STAGE_BLOCKS", "1")
    skel = {"title": "Wniosek o test", "applicant_kinds": ["person"], "dropped": good()["dropped"],
            "pages": [{"title": "Zwrot", "sections": [{"title": "Sposób", "src": ["p1.b1-p1.b2"]}]}]}
    page = {"title": "Zwrot", "sections": good()["pages"][0]["sections"]}
    p = ByModel({("small", True): skel, ("small", False): page, ("large", True): skel, ("large", False): page})
    r = extract(DOC, provider=p)
    assert {m for m, c in p.calls if "PIERWSZY ETAP" in c} == {"small", "large"}  # both first passes were started
    assert [s["model"] for s in r.trace if s.get("stage") == "extract"] == ["small"] and r.trace[-1]["accepted"]


def test_lost_paper_section_is_filled_by_a_short_call_before_any_repair():
    texts = list(BLOCKS.values()) + ["C. OKOLICZNOŚCI ZŁOŻENIA", "Data zdarzenia ___"]
    d = doc(texts)
    first = good()
    page = {"title": "", "sections": [{"title": "Okoliczności", "fields": [
        {"key": "data", "label": "Data zdarzenia", "source_label": "Data zdarzenia", "type": "DATEPICKER", "src": ["p1.b6"]}]}]}
    p = Fake([first, page])
    r = extract(d, provider=p)
    assert [t["round"] for t in r.trace] == ["first", "fill"] and r.trace[-1]["accepted"], r.trace
    assert "[p1.b0]" not in p.calls[1][1] and "[p1.b6]" in p.calls[1][1]  # the fill call sees only the lost part
    assert [s.title for s in r.tree.pages[0].sections][-1] == "Okoliczności"
