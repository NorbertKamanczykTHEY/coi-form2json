"""ParsedDocument -> FieldTree + needs_review (design: docs/design/field-extraction.md).

Ladder (Q1): each rung from config("extraction.ladder") gets a first attempt and one repair round with the gate's
objections; a rejected rung escalates to the next. If no rung passes the gate, the best tree comes back with the gate's
objections in needs_review. Long or multi-variant documents (Q2, #9) go two-stage: a skeleton of pages/sections/variants,
then fields page by page with the skeleton as fixed input.
"""
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Literal

from openai import BadRequestError
from pydantic import BaseModel, Field, ValidationError

from coi import llm
from coi.config import Config, config
from coi.parsing.model import ParsedDocument
from coi.prompts import prompt

from .anchors import anchored, blocks_of, expand
from .gate import gate, norm
from .postprocess import normalize
from .tree import Addressee, Consent, Drop, FieldTree, FormField, Section, ShowIf, StrList, SubjectPage

OnEvent = Callable[[str, dict], None]
VARIANT = re.compile(r"^\W*wniosek o\b", re.I)
VARIANT_KEY = "rodzaj_wniosku"


class ExtractionError(RuntimeError):
    """No rung produced a tree that passes the schema (G1)."""


@dataclass
class ExtractionResult:
    tree: FieldTree
    needs_review: list[dict]
    trace: list[dict] = field(default_factory=list)
    cost: float = 0.0


class SkeletonSection(BaseModel):
    title: str
    src: list[str] = Field(description="zakresy kotwic bloków sekcji, np. ['p1.b24-p1.b59']")
    variants: StrList = Field(default_factory=list, description="rodzaje wniosków, których dotyczy sekcja; pusto = wspólna")
    repeating: bool = False
    person_role: Literal["third_party"] | None = None


class SkeletonPage(BaseModel):
    title: str
    sections: list[SkeletonSection]


class Skeleton(BaseModel):
    title: str
    addressee: Addressee | None = None
    applicant_kinds: list[Literal["person", "legal_entity"]]
    entity_option: str | None = None
    variants: StrList = Field(default_factory=list, description="krótkie nazwy rodzajów wniosków, gdy dokument łączy kilka; inaczej pusto")
    pages: list[SkeletonPage]
    consents: list[Consent] = Field(default_factory=list)
    dropped: list[Drop] = Field(default_factory=list)
    issues: StrList = Field(default_factory=list)


class _Calls:
    """LLM calls of one extract(): schema check + one schema repair per call, cost and time summed (thread-safe)."""

    def __init__(self, provider: llm.Provider, max_tokens: int):
        self.provider, self.max_tokens = provider, max_tokens
        self.cost = self.seconds = 0.0
        self.n = 0
        self._lock = threading.Lock()

    def _chat(self, model: str, text: str, schema: dict, name: str) -> llm.Reply:
        rf = {"type": "json_schema", "json_schema": {"name": name, "schema": schema}}
        try:
            r = self.provider.chat(model, text, self.max_tokens, response_format=rf)
        except BadRequestError:  # provider without json_schema support: schema is in the prompt anyway
            r = self.provider.chat(model, text, self.max_tokens, response_format={"type": "json_object"})
        with self._lock:
            self.cost += r.cost
            self.seconds += r.seconds
            self.n += 1
        return r

    def ask[T: BaseModel](self, model: str, text: str, cls: type[T]) -> T:
        msg = text
        for _ in range(2):  # Eden does not enforce json_schema: validate, one repair with the errors (G1)
            r = self._chat(model, msg, cls.model_json_schema(), cls.__name__)
            body = re.sub(r"^```(?:json)?|```$", "", r.text.strip(), flags=re.M).strip()
            try:
                return cls.model_validate_json(body)
            except ValidationError as e:
                err = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()[:15])
                if r.finish == "length":
                    err = f"odpowiedź ucięta na limicie tokenów, skróć ją; {err}"
                msg = prompt("field_extraction_repair", base=text, errors=err, previous=body[:20000])
        raise ExtractionError(f"{model}: reply does not match {cls.__name__} after a repair: {err[:300]}")


def _variant_headings(blocks: dict[str, str]) -> list[str]:
    return [a for a, t in blocks.items() if VARIANT.match(t)]


def _single(calls: _Calls, model: str, doc: ParsedDocument) -> FieldTree:
    return calls.ask(model, _base_prompt(doc), FieldTree)


def _base_prompt(doc: ParsedDocument) -> str:
    return prompt("field_extraction", schema=json.dumps(FieldTree.model_json_schema(), ensure_ascii=False), text=anchored(doc))


def _two_stage(calls: _Calls, model: str, doc: ParsedDocument, blocks: dict[str, str], workers: int) -> FieldTree:
    skel = calls.ask(model, prompt("field_extraction_skeleton", schema=json.dumps(Skeleton.model_json_schema(), ensure_ascii=False),
                                   text=anchored(doc)), Skeleton)
    variants = skel.variants if len(skel.variants) >= 2 else []
    fixed = skel.model_dump_json(include={"title", "variants", "pages"}, exclude_none=True)
    rule = (f"Sekcje z niepustym `variants` dostaną `show_if` na pole `{VARIANT_KEY}` (opcje: {variants}) automatycznie: "
            "nie dodawaj pola „Rodzaj wniosku” i nie ustawiaj show_if na rodzaj wniosku.") if variants else ""
    schema = json.dumps(SubjectPage.model_json_schema(), ensure_ascii=False)

    def fields_of(sp: SkeletonPage) -> SubjectPage:
        only = set(expand([a for s in sp.sections for a in s.src], blocks))
        return calls.ask(model, prompt("field_extraction_page", skeleton=fixed, page=sp.title, variant_rule=rule,
                                       schema=schema, text=anchored(doc, only)), SubjectPage)

    with ThreadPoolExecutor(max(1, workers)) as ex:
        pages = list(ex.map(fields_of, skel.pages))
    for sp, page in zip(skel.pages, pages):
        page.title = sp.title
        by_title = {norm(s.title): s for s in sp.sections}
        for i, sec in enumerate(page.sections):
            sk = by_title.get(norm(sec.title)) or (sp.sections[i] if i < len(sp.sections) else None)
            if not sk:
                continue
            sec.src = sec.src or sk.src
            sec.repeating = sec.repeating or sk.repeating
            sec.person_role = sec.person_role or sk.person_role
            opts = [v for v in sk.variants if v in variants]
            if opts and set(opts) != set(variants) and not sec.show_if:  # Q2: variant sections are SHOW, not copies
                sec.show_if = ShowIf(field=VARIANT_KEY, options=opts)
    pages = [p for p in pages if p.sections]
    if variants and pages:
        heads = _variant_headings(blocks)
        pages[0].sections.insert(0, Section(title="Rodzaj wniosku", src=heads, fields=[FormField(
            key=VARIANT_KEY, label="Wybierz rodzaj wniosku", source_label=blocks.get(heads[0], "Wniosek o") if heads else "Wniosek o",
            type="RADIO", options=variants, src=heads[:1])]))
    return FieldTree(title=skel.title, addressee=skel.addressee, applicant_kinds=skel.applicant_kinds, entity_option=skel.entity_option,
                     pages=pages, consents=skel.consents, dropped=skel.dropped, issues=skel.issues)


def extract(doc: ParsedDocument, on_event: OnEvent | None = None, provider: llm.Provider | None = None) -> ExtractionResult:
    cfg = config("extraction")
    provider = provider or llm.provider(Config.load())
    emit = on_event or (lambda *_: None)
    blocks = blocks_of(doc)
    two_stage = len(blocks) > cfg["two_stage_blocks"] or len(_variant_headings(blocks)) > 1
    mode = "two_stage" if two_stage else "single"
    calls = _Calls(provider, cfg["max_tokens"])
    trace: list[dict] = []
    best = None  # (number of gate objections, tree, review, gate)
    for rung, model in enumerate(cfg["ladder"]):
        step = {"stage": "extract", "mode": mode, "rung": rung, "model": model}
        cost0, secs0, n0 = calls.cost, calls.seconds, calls.n
        try:
            tree = _two_stage(calls, model, doc, blocks, cfg["workers"]) if two_stage else _single(calls, model, doc)
        except ExtractionError as e:
            trace.append(step | {"round": "first", "accepted": False, "error": str(e), "cost": round(calls.cost - cost0, 5)})
            emit("escalation", {"step": f"extract.{rung}", "model": model, "accepted": False, "error": str(e)})
            continue
        for rnd in ("first", "repair"):
            tree, review = normalize(tree, blocks)
            g = gate(tree, blocks)
            trace.append(step | {"round": rnd, "accepted": g["ok"], "fails": g["fails"], "coverage": g["coverage"],
                                 "calls": calls.n - n0, "cost": round(calls.cost - cost0, 5), "seconds": round(calls.seconds - secs0, 1)})
            emit("escalation", {"step": f"extract.{rung}.{rnd}", "model": model, "accepted": g["ok"], "error": "; ".join(g["fails"]) or None})
            if best is None or len(g["fails"]) <= best[0]:  # ties: the later (stronger) attempt
                best = (len(g["fails"]), tree, review + g["needs_review"], g)
            if g["ok"] or rnd == "repair":
                break
            cost0, secs0, n0 = calls.cost, calls.seconds, calls.n
            base = _base_prompt(doc)  # repair is one full call even for two-stage trees (#9 fits: ~9k tokens in)
            try:
                tree = calls.ask(model, prompt("field_extraction_repair", base=base, errors="\n".join(g["fails"]),
                                               previous=tree.model_dump_json(exclude_none=True)), FieldTree)
            except ExtractionError as e:
                trace.append(step | {"round": "repair", "accepted": False, "error": str(e), "cost": round(calls.cost - cost0, 5)})
                break
        if best[3]["ok"]:
            break
    if best is None:
        raise ExtractionError("no rung of the extraction ladder returned a valid FieldTree")
    _, tree, review, g = best
    review += [{"why": f"quality gate: {f}"} for f in g["fails"]]  # no rung passed: hand the best tree to a human
    return ExtractionResult(tree=tree, needs_review=review, trace=trace, cost=round(calls.cost, 5))
