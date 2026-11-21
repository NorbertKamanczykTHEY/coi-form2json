"""Contract: ParsedDocument -> FieldTree (LLM output, validated by Pydantic) -> generator.

Pydantic, not dataclasses: openai already pulls it in, and one class gives both the JSON Schema for structured output
and the validation of the reply. Every node carries `src` anchors (p<page>.b<block>) -> editor.field_map for free.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, model_validator

StrList = Annotated[list[str], BeforeValidator(lambda v: v or [])]  # models send null for empty lists


FieldType = Literal["TEXT_FIELD", "TEXTAREA", "NUMBER", "DATEPICKER", "RADIO", "CHECKBOX", "SELECT", "FILE_UPLOADER", "TEXT_BLOCK"]
Preset = Literal["first_name", "last_name", "pesel", "birth_date", "id_card", "address", "phone", "email", "bank_account"]
DropReason = Literal[
    "applicant_data",  # wnioskodawca: imię/nazwisko/nazwa, PESEL/NIP, adres -> strona „Dane” (S2-S6)
    "proxy_data",  # pełnomocnik / reprezentant -> „Dane” (S5)
    "contact",  # telefon, e-mail wnioskodawcy -> „Kontakt i zgody” (S7)
    "addressee",  # adresat / adres urzędu (S1)
    "signature_date",  # miejscowość, data, podpis (S10)
    "office_use",  # wypełnia organ, pieczęć (S10)
    "legal_info",  # podstawa prawna, pouczenia, instrukcja wypełniania, informacje o opłacie (S10, S15)
    "rodo",  # klauzula informacyjna (S10)
    "title",  # nagłówek „WNIOSEK …”
    "template_attachment",  # pełnomocnictwo, dowód opłaty skarbowej (S12)
    "empty_slot",  # puste pozycje listy „2) ___ 3) ___”
    "consent",  # oświadczenie przeniesione do `consents` (S11)
]


class ShowIf(BaseModel):
    field: str = Field(description="`key` pola sterującego (RADIO/CHECKBOX/SELECT)")
    options: StrList = Field(description="dokładne nazwy opcji pola sterującego; element widoczny, gdy wybrano którąkolwiek")
    negate: bool = Field(default=False, description="true: widoczny, gdy NIE wybrano żadnej z tych opcji")

    @model_validator(mode="before")
    @classmethod
    def _single(cls, v):  # models (and the first spike runs) send {"option": "..."}
        if isinstance(v, dict) and "option" in v and "options" not in v:
            v = {**v, "options": [v.pop("option")]}
        return v


class FormField(BaseModel):
    key: str = Field(description="unikalny identyfikator snake_case bez polskich znaków")
    label: str = Field(description="etykieta w e-formularzu: zdanie, neutralna płciowo, bez dwukropka i numeracji")
    source_label: str = Field(description="etykieta dosłownie jak w tekście źródłowym")
    type: FieldType
    options: StrList = Field(default_factory=list, description="opcje RADIO/CHECKBOX/SELECT; pusto dla innych typów")
    preset: Preset | None = Field(default=None, description="typowe pole osobowe/adresowe osoby trzeciej")
    show_if: ShowIf | None = None
    optional_evidence: str | None = Field(default=None, description="dosłowny cytat ze źródła mówiący, że pole jest nieobowiązkowe (np. 'opcjonalnie', 'można dołączyć'); null gdy brak")
    multiple: bool = Field(default=False, description="FILE_UPLOADER: wnioskodawca może dodać kilka plików")
    default_value: str | None = Field(default=None, description="wartość stała wydrukowana na papierze (S15)")
    description: str | None = Field(default=None, description="krótka podpowiedź dla wypełniającego")
    description_source: Literal["document", "ai"] | None = Field(default=None, description="'document' gdy podpowiedź pochodzi z tekstu źródła, 'ai' gdy to Twoja sugestia; kod to weryfikuje")
    doubt: str | None = Field(default=None, description="krótko, jeśli interpretacja pola jest niepewna")
    src: StrList = Field(default_factory=list, description="kotwice bloków źródłowych, np. ['p1.b12']")


class Section(BaseModel):
    title: str
    repeating: bool = Field(default=False, description="true gdy źródło każe powtarzać blok (np. 'dla każdego psa', numerowane identyczne bloki)")
    person_role: Literal["third_party"] | None = Field(default=None, description="'third_party' gdy sekcja to dane osoby trzeciej (nie wnioskodawcy, nie pełnomocnika)")
    show_if: ShowIf | None = None
    fields: Annotated[list[FormField], BeforeValidator(lambda v: v or [])] = Field(default_factory=list)
    src: StrList = Field(default_factory=list)


class SubjectPage(BaseModel):
    title: str = Field(description="tytuł strony od treści, np. 'Informacje o nadpłacie'")
    sections: Annotated[list[Section], BeforeValidator(lambda v: v or [])] = Field(default_factory=list)


class Consent(BaseModel):
    text: str = Field(description="treść oświadczenia w formie neutralnej płciowo, np. 'Oświadczam, że…'")
    show_if: Annotated[list[ShowIf], BeforeValidator(lambda v: [] if not v else [v] if isinstance(v, dict) else v)] = Field(
        default_factory=list, description="warunki (wszystkie naraz), gdy zgoda dotyczy tylko jednego rodzaju wniosku albo jednej sytuacji; pusto = zawsze")
    src: StrList = Field(default_factory=list)


class Drop(BaseModel):
    reason: DropReason
    src: StrList = Field(default_factory=list)


class Addressee(BaseModel):
    kind: Literal["organ", "office"] = Field(description="organ: Wójt/Burmistrz/Prezydent; office: Urząd …")
    name: str = Field(description="nazwa organu albo urzędu, z wydziałem jeśli podany")
    src: StrList = Field(default_factory=list)


class FieldTree(BaseModel):  # defaults everywhere: the prompt tells models to omit null and empty lists
    title: str = Field(description="tytuł e-formularza zaczynający się od Wniosek/Zgłoszenie/Deklaracja/Oświadczenie")
    addressee: Addressee | None = None
    applicant_kinds: list[Literal["person", "legal_entity"]] = Field(description="kim może być wnioskodawca: person = osoba fizyczna, legal_entity = firma/instytucja (NIP, REGON, nazwa)")
    entity_option: str | None = Field(default=None, description="tekst opcji wyboru podmiotu z papieru, gdy formularz każe zaznaczyć rodzaj wnioskodawcy (np. 'Klub sportowy'); null gdy brak (P2a)")
    pages: list[SubjectPage] = Field(description="tylko strony przedmiotu wniosku, bez danych wnioskodawcy, kontaktu i zgód")
    consents: Annotated[list[Consent], BeforeValidator(lambda v: v or [])] = Field(default_factory=list)
    dropped: Annotated[list[Drop], BeforeValidator(lambda v: v or [])] = Field(default_factory=list)
    issues: StrList = Field(default_factory=list, description="niespójności w źródle (S17)")
