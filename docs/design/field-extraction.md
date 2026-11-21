# Ekstrakcja pól: ParsedDocument → drzewo przedmiotu wniosku

Status: projekt do omówienia · 2026-11-21 · spike: `app/spikes/field-extraction/`

## 0. Decyzje użytkownika (2026-11-21)
| # | Decyzja | Gdzie |
|---|---|---|
| Q1 | Model: **drabinka mistral-small → mistral-large**. Po odrzuceniu przez bramkę: runda naprawy z zarzutami bramki (ten sam szczebel), potem następny szczebel, na końcu wynik z `needs_review`. Szczeble w konfiguracji (jak `ladder.json` parsera), nie w kodzie | §5 |
| Q2 | **Dwuetapowa ekstrakcja** dla długich i wielowariantowych dokumentów: najpierw szkielet stron i sekcji (warianty, sekcje wspólne, role bloków), potem pola osobno dla każdej sekcji, ze szkieletem jako stałym wejściem. Krótkie dokumenty: jedno wywołanie | §5 |
| Q3 | Podpowiedzi wymyślone przez LLM zostają w `description` z oznaczeniem **sugestia AI**: `description_source: "document" \| "ai"`. Kod sprawdza cytatem: gdy treści nie ma w źródle, wpisuje `"ai"` niezależnie od tego, co podał model. Generator przenosi to do `field_map` jako sugestię do akceptacji urzędnika w edytorze, **nie** do `needs_review` | §2, `postprocess.py` |
| P1 | „należy załączyć”, „należy dołączyć”, „do wniosku załączam”, „w załączeniu” i podobne **zawsze** dają pole FILE_UPLOADER. Wyjątek (nasza interpretacja): pełnomocnictwo i dowód opłaty skarbowej, bo są już w szablonie „Dane” | prompt |
| P2 | Wybór wnioskodawcy lub podmiotu, który papier daje jako pola wyboru (#9 „Prezydent Miasta / Klub sportowy”, „☐ Dane reprezentanta ☐ Dane pełnomocnika”), to **CHECKBOX z polami zależnymi przez `show_if`**, nigdy RADIO z jedną opcją | prompt |
| P1a | Pełnomocnictwo i dowód opłaty skarbowej są w szablonie „Dane” (S12), więc w przedmiocie **nie** dostają FILE_UPLOADER | prompt (już tak jest) |
| P2a | Wybór wnioskodawcy z #9 („Prezydent Miasta / Klub sportowy”) **zostaje w szablonie** (S4, Q20). Ekstrakcja oddaje tylko rodzaj wnioskodawcy (`applicant_kinds`) i tekst opcji z papieru („Klub sportowy”). Generator wstawia z niego CHECKBOX w szablonie przez `{{entity_option}}`. „Prezydent Miasta” odpada. **Przy implementacji:** dodać do FieldTree pole `entity_option: str \| None` (tekst opcji podmiotu z papieru) i punkt w prompcie | `tree.py`, prompt |

## 1. Gdzie to siedzi
```
parse() → ParsedDocument ─► [A] tekst z kotwicami ─► [B] LLM: FieldTree ─► [C] bramka ─► [D] normalize ─► FieldTree + needs_review ─► generator
                                  (kod)                 (1 wywołanie)        (kod)          (kod, reguły wymagające tekstu źródła)
```
- **[A] Kotwice.** Każdy blok dostaje kotwicę `[p<strona>.b<indeks>]`. LLM cytuje kotwice w `src`, więc `editor.field_map` (A4 w `api-assumptions.md`) powstaje bez dodatkowej pracy: pole → strona, blok, a dla OCR także bbox i confidence z bloku. Kontrakt `ParsedDocument` zostaje bez zmian.
- **[B] LLM** robi to, czego nie da się zapisać regułą: dzieli bloki na szablon i przedmiot, grupuje pola w sekcje i strony, rozpoznaje typy, opcje, zależności, sekcje powtarzalne i osoby trzecie.
- **[C] Bramka** (kod, bez wzorca) decyduje: przyjąć, naprawić albo eskalować.
- **[D] Normalize** (kod, `postprocess.py`) poprawia FieldTree regułami, które potrzebują tekstu źródła (generator go nie widzi): weryfikacja znaczników opcjonalności, R4, puste sloty załączników, `___` w opcjach, polskie i unikalne `key`, presety z etykiet. Wynik ma **ten sam kształt** FieldTree.

## 2. Model drzewa (wyjście LLM)
Pydantic: `openai` już go instaluje, a jedna klasa daje JSON Schema dla structured output i walidację odpowiedzi. Plik: `spikes/field-extraction/tree.py`.

```python
class FormField(BaseModel):
    key: str                      # id dla odwołań show_if (techName robi kod z label)
    label: str                    # etykieta e-formularza („Numer rachunku”)
    source_label: str             # dosłownie ze źródła, do sprawdzenia ugruntowania
    type: Literal["TEXT_FIELD","TEXTAREA","NUMBER","DATEPICKER","RADIO","CHECKBOX","SELECT","FILE_UPLOADER","TEXT_BLOCK"]
    options: list[str] = []
    preset: Literal["first_name","last_name","pesel","birth_date","id_card","address","phone","email","bank_account"] | None
    show_if: ShowIf | None        # {field: key, options: ["…"], negate: false}
    optional_evidence: str | None # dosłowny cytat znacznika opcjonalności (R2), kod go weryfikuje
    default_value: str | None     # stała z papieru (S15)
    description: str | None
    description_source: Literal["document","ai"] | None  # kod weryfikuje cytatem (Q3)
    doubt: str | None             # R7: niepewność → needs_review
    src: list[str]                # ["p1.b13"]

class Section(BaseModel):
    title: str; repeating: bool; person_role: Literal["third_party"] | None
    show_if: ShowIf | None; fields: list[FormField]; src: list[str]

class FieldTree(BaseModel):
    title: str
    addressee: {kind: "organ"|"office", name, src}   # S1 / S1b
    applicant_kinds: list["person"|"legal_entity"]  # S2 / S3 / S4
    pages: list[{title, sections}]                  # tylko przedmiot wniosku
    consents: list[{text, src}]                     # S11 → „Kontakt i zgody”
    dropped: list[{reason, src}]                    # wszystko, co trafia do szablonu albo jest usuwane (S1–S10)
    issues: list[str]                               # S17
```
`dropped` jest po to, żeby bramka mogła rozliczyć każdy blok z miejscem do wypełnienia: albo jest polem, albo został świadomie usunięty z powodem.

## 3. Uzgodnienie z generatorem (wątek „Generator JSON COI”)
Generator (`app/docs/design/generator.md` §1) przyjmuje **FieldTree bez zmian w kształcie** i sam robi: techName z `key` (z kolizjami), presety → walidatory i bloki adresu, `required = optional_evidence is None` → `validation`, `show_if` → JSONata, `addressee`/`applicant_kinds` → wariant strony „Dane”, `src`/`doubt` → `field_map`. Zgadzamy się w całości. Jedyna różnica: ekstrakcja oddaje FieldTree **po** kroku [D], bo tylko ona ma tekst źródła.

Prośby generatora, wszystkie przyjęte (są w `tree.py` i w prompcie):
1. `show_if = {field, options: [..], negate}` zamiast pojedynczej `option`. Stara forma `{option}` jest nadal przyjmowana.
2. `key` unikalny w całym drzewie: [D] nadaje `key` = slug polskiej etykiety (`numer_rachunku`), bo LLM w połowie przypadków nadaje klucze po angielsku.
3. Pole spoza sekcji powtarzalnej nie zależy od pola wewnątrz niej: bramka G12 to sprawdza (eskalacja).

**Test end to end:** `bridge_to_generator.py` (tłumaczenie według tabeli z `generator.md` §1; docelowo to adapter po stronie generatora) → `app/spikes/generator/gen.py` → `validate.py`. Drzewa z mistral-large dla #1, #3, #5 i #7 oraz #9 przechodzą walidator (JSON Schema, reguły 1–6, referencje JSONaty): `out/e2e/*.coi.json`. Strona przedmiotu #5 ma te same pola, typy, opcje radia i dwa SHOW co wzorzec.

Do ustalenia z generatorem: kto robi adapter (tabela z `generator.md` §1 w kodzie generatora, wtedy `bridge_to_generator.py` znika) i gdzie trafia `needs_review` z [D] (proponuję: generator scala je z `doubt` do `field_map[fieldId].needs_review`).

## 4. LLM kontra kod
| Decyzja | Kto | Dlaczego |
|---|---|---|
| Blok to szablon czy przedmiot (S1–S10), rola osoby (wnioskodawca / pełnomocnik / osoba trzecia) | LLM | zależy od sensu („Dane innej osoby” kontra „właściciel rachunku”) |
| Grupowanie w sekcje i strony, tytuły stron | LLM | kod sprawdza tylko: strona ≥ 1 pole, brak duplikatów sekcji |
| Typ pola, opcje, S13 („inne ___” → opcja + pole SHOW), S14, powtarzalność | LLM | zapis na papierze jest zbyt różnorodny dla regexów |
| Obligatoryjność R1–R4, R7 | **kod** [D] | LLM podaje tylko cytat `optional_evidence`; kod zostawia go, gdy cytat jest w źródle i pasuje do listy znaczników, inaczej czyści i flaguje. „należy dołączyć” → wymagany. Generator: `required = optional_evidence is None` |
| Preset z etykiety (PESEL, e-mail, seria i numer dowodu, data urodzenia), „Data…” → DATEPICKER | **kod** [D] | etykieta; walidatory z presetu dokłada generator |
| Polski i unikalny `key`, czyszczenie opcji z `___`, puste sloty załączników „2) ___” | **kod** [D] | deterministyczne; techName z `key` robi generator |
| Słowniki (Kraje, TERYT, nowe) | **kod**: katalog + aliasy; LLM-sędzia K1–K3 tylko bez dopasowania (flow-review §4) | bez halucynacji pozycji |
| Presety osoby trzeciej i adresu | LLM wskazuje `preset`, generator rozwija szablon | jedna definicja adresu dla całego systemu |

## 5. Prompt i liczba wywołań
**Decyzje Q1 i Q2 są nadrzędne wobec tej sekcji:** drabinka small → large z rundą naprawy i dwuetapowa ekstrakcja dla długich i wielowariantowych dokumentów. Kryterium „długi lub wielowariantowy” ustalimy przy implementacji (propozycja: > 150 bloków albo więcej niż jedno „Wniosek o…” w nagłówkach). Poniżej: co pokazał spike przy jednym wywołaniu.

**Jedno wywołanie na dokument** (prompt `spikes/field-extraction/field_extraction.md`, w produkcji `app/backend/coi/prompts/field_extraction.md`; kod tylko wczytuje plik i podstawia `{schema}` i `{text}`: reguły S1–S17 i R2 w 13 punktach, schemat i tekst z kotwicami). Powody:
- zależności `show_if` i warianty #9 łączą odległe części dokumentu, a podział na kawałki je rozrywa;
- #9 (najdłuższy, 257 bloków, ok. 16 tys. znaków) mieści się w jednym wywołaniu: ok. 9 tys. tokenów wejścia, 47–90 s.
- Naprawa: gdy odpowiedź nie przejdzie walidacji Pydantic, jedno ponowienie z listą błędów (ten sam model). Gdy bramka odrzuci wynik, eskalacja do mocniejszego modelu.
- Etapy dokładamy dopiero, gdy będą potrzebne: (a) wstępne cięcie RODO i pouczeń regułą (#7: 36 z 60 bloków to RODO), żeby skrócić wejście; (b) dla dokumentów powyżej limitu kontekstu podział po nagłówkach poziomu 1 ze wspólnym kontekstem („klucze pól sterujących”). Na materiałach konkursowych żadne nie było potrzebne.
- `Provider.chat()` w `coi/llm.py` nie ma parametru `response_format`. Spike używa klienta OpenAI pod spodem. Produkcja potrzebuje `chat(..., response_format=None)`, to prośba do wątku backendu.
- Limit wyjścia, nie wejścia, ogranicza długie dokumenty: mistral-large na #9 przy `max_tokens` 12k ucięło odpowiedź (179 s, $0.046 za 3 próby). Przy 24k i regule „pomijaj null i puste listy” zmieściło się w 91 s za $0.023. Domyślnie `max_tokens` = 24k.
- `json_schema` w `response_format` Eden przyjmuje, ale **go nie wymusza** (modele zwracały `null` w listach i strony bez `sections`). Dlatego walidacja Pydantic i naprawa są obowiązkowe.

## 6. Bramka jakości (bez wzorca)
| # | Sprawdzenie | Skutek |
|---|---|---|
| G1 | Zgodność ze schematem (Pydantic) | 1 naprawa, potem eskalacja |
| G2 | Każda kotwica istnieje | eskalacja |
| G3 | **Pokrycie**: każdy blok z `___` lub `☐` jest cytowany przez pole, sekcję, zgodę albo `dropped` | > 10% niepokrytych → eskalacja; pojedyncze → `needs_review` |
| G4 | `show_if` wskazuje istniejące pole i istniejącą opcję | eskalacja |
| G5 | RADIO/CHECKBOX/SELECT mają ≥ 2 opcje | eskalacja |
| G6 | Ta sama sekcja na kilku stronach bez `show_if` (warianty #9 skopiowane zamiast SHOW) | eskalacja |
| G7 | Ugruntowanie: `source_label` znaleziony (fuzzy) w cytowanym bloku ± 1 | `needs_review` |
| G8 | Pole przedmiotu wygląda na dane wnioskodawcy (imię, PESEL, telefon) poza sekcją osoby trzeciej | `needs_review` |
| G9 | Pole szczegółowe wewnątrz bloku wyboru bez `show_if` | `needs_review` (parser skleja wiersze, więc za dużo fałszywych alarmów na blokadę) |
| G10 | Znacznik opcjonalności podany przez LLM, którego nie ma w źródle; `doubt` | `needs_review`, pole zostaje wymagane (R7) |
| G11 | Powód w `dropped` nie pasuje do bloku: blok z `___` usunięty jako `legal_info`/`rodo`/`title`, „załącznik szablonu”, który nie jest pełnomocnictwem ani opłatą | eskalacja. To złapało oba przypadki „bramka przepuściła, a brakowało pola” (#5: korekta deklaracji i kwota usunięte jako szablon) |
| G12 | `show_if` spoza sekcji powtarzalnej wskazuje pole wewnątrz niej | eskalacja (JSONata COI tego nie wyrazi) |

`needs_review` trafia do `report.needs_review` i do `field_map[techName].needs_review`, żeby edytor podświetlił pole i blok źródłowy.

## 7. Wyniki spike'a
Wejście: tekst z parsera backendu (Kreuzberg, docx) z kotwicami. Złoty zbiór pól przedmiotu w `gold_subject.json`: #1 i #5 z JSON wzorców, #3 i #7 spisane ręcznie z flow-review §5. Każdy model × formularz uruchomiony 2 razy (temperatura 0). Skrypty: `parse_inputs.py`, `extract.py`, `table.py`, pełna tabela w `out/table.md`.

**Modele na #1, #3, #5 i #7 (8 przebiegów na model):**

| Model | Pełny recall (8) | Średni recall | Bramka ok | Błąd schematu po naprawie | Śr. czas | Śr. koszt |
|---|---|---|---|---|---|---|
| **mistral-large-2512** | **8** | **1.00** | **7** | 0 | 12 s | $0.0028 |
| mistral-small-2603 | 5 | 0.80 | 3 | 1 (#7) | 9 s | $0.0012 |
| ministral-14b-2512 | 5 | 0.94 | 1 | 0 | 16 s | $0.0005 |
| gemma-4-31b-it | 3 | 0.79 | 2 | 0 | 6 s | $0.0006 |
| Qwen3-VL-30B-A3B | 4 | 0.88 | 2 | 0 | 78 s | $0.0016 |

**Formularz → mistral-large (przebiegi 1/2):**

| # | Recall | Typy | Opcje | show_if | Powtarzalna | Czas | Koszt |
|---|---|---|---|---|---|---|---|
| 1 | 4/4 | 100% | – | – | – | 8–9 s | $0.002–0.004 |
| 3 | 3/3 | 100% | 100% / 80% | 1/1 | – | 7 s | $0.0015 |
| 5 | 7/7 | 100% | 100% | 2/2 (ręcznie; skrypt liczy 1/2, bo myli dwa pola „z tytułu”) | – | 14–15 s | $0.003–0.004 |
| 7 | 11/11 | 100% | 100% | 2/2 | tak, 3 oświadczenia → zgody | 17 s | $0.003–0.004 |
| 9 | bez wzorca; 94 pola, pokrycie 0.93, bramka **odrzuca** | | | | | 91 s (24k) | $0.023 |

**Bramka a wzorzec (39 drzew z wynikiem):** 0 fałszywych akceptacji (bramka nie przepuściła żadnego drzewa z brakującym polem). 15 dobrych przepuściła, 14 złych odrzuciła, 10 dobrych odrzuciła (niepokryte `___` daty, `show_if` na nieistniejącą nazwę opcji, `___` usunięte jako szablon). Fałszywe odrzucenie kosztuje jedną dodatkową próbę, czyli kilka groszy.

**#9 (16 stron, 3 wnioski w 1):** żaden model nie dał drzewa, które przechodzi bramkę. mistral-small i mistral-large poprawnie dodają radio „Rodzaj wniosku” i sekcję powtarzalną podopiecznych, ale: dane klubu, reprezentanta i pełnomocnika lądują w przedmiocie (S4 mówi: szablon), sekcje wspólne są kopiowane per wariant zamiast SHOW, checkboxy „Dane reprezentanta / pełnomocnika” nie mają opcji. Bramka to łapie (G3, G5, G6, G8).

**Rekomendacja modelu (zastąpiona decyzją Q1: drabinka small → large):** spike wskazywał **mistral-large-2512** jako jedyny szczebel. Drabinka small → large kosztuje tyle samo (ok. $0.0012 + 5/8 × $0.0028 ≈ $0.003 na formularz), a przy porażce trwa dłużej. Eskalacja po odrzuceniu: (1) jedna runda naprawy z listą zarzutów bramki w prompcie (ten sam model, nieprzetestowane), (2) jeśli dalej źle, wynik z `needs_review` zamiast błędu. Koszt na 6 formularzy konkursowych: ok. $0.04 (z #9). Wydane na spike: ok. $0.16.

**End to end:** LLM → bramka → normalize → `gen.py` → `validate.py` przechodzi dla wszystkich 5 drzew mistral-large (§3).

## 8. Ryzyka
- **#9 i inne dokumenty wielowariantowe** to główne ryzyko jakości. Pomysł (nieprzetestowany): dla dokumentów, w których LLM zwróci radio „Rodzaj wniosku”, osobne pierwsze wywołanie „szkielet” (warianty, bloki wspólne, role bloków), potem wywołanie pól z tym szkieletem jako stałym wejściem. Alternatywa: runda naprawy z zarzutami bramki.
- **Niedeterminizm przy temperaturze 0:** mistral-small na #3 dał raz 3/3, raz 2/3 pól. Bramka i eskalacja są dlatego obowiązkowe, nie opcjonalne.
- **Mała próba:** 4 formularze ze wzorcem (2 ręczne), po 2 przebiegi, dopasowanie przez aliasy. Wynik „mistral-large 8/8” jest kierunkowy, nie statystyczny.
- **Eden nie wymusza `json_schema`:** walidacja Pydantic i runda naprawy są konieczne. mistral-small na #7 nie dał poprawnego schematu nawet po 2 naprawach.
- **LLM dopisuje podpowiedzi**, których nie ma w źródle („Podaj kwotę w złotych”, „w formacie NRB”). Są sensowne, ale nieugruntowane.
- **Artefakty parsera:** sklejone wiersze („NIP * ___ Urząd Gminy”, cała tabela psa w jednym bloku), `# PESEL` jako nagłówek. LLM sobie radzi, ale przez to G9 jest tylko sygnałem do przeglądu.
- **Lokalny fallback:** mistral-large to model open-weights (Mistral 3, do potwierdzenia licencji), ale za duży na laptopa. Lokalnie realny jest ministral-14b, który w spike'u przechodził bramkę 1/8 razy. Lokalnie wyniki byłyby głównie z `needs_review`.

## 9. Pytania
Rozstrzygnięte (§0): Q1, Q2, Q3. Adapter FieldTree → model generatora robi generator; `bridge_to_generator.py` zostaje jako test kontraktu. `response_format` w `Provider.chat()` przejął wątek backendu. `needs_review` z `normalize` generator scala z `doubt` w `field_map[fieldId].needs_review`. Kolizje kluczy: sufiks `_2`.

Do zrobienia przy implementacji:
1. `entity_option` w FieldTree i w prompcie (P2a).
2. #7: pole „Kopia książeczki szczepień” wypadło poza sekcję powtarzalną psa, choć papier mówi „kopia dla każdego psa”. Do rozwiązania w prompcie („załącznik dotyczący każdego elementu powtarzalnego należy do tej sekcji”) albo w bramce (FILE_UPLOADER, którego `src` mówi „dla każdego”/„każdego psa”, poza sekcją `repeating` → `needs_review`).
3. #9: bloki wariantów z `___` usuwane z niewłaściwym powodem (G11) i strona „Dane sportowca” bez `show_if` na rodzaj wniosku. To ma rozwiązać dwuetapowa ekstrakcja (Q2).
