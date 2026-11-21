# Brief: implementacja rdzenia (ekstrakcja pól + generator JSON COI)

Dwa wątki, które zaprojektowały rdzeń, teraz go implementują w `app/backend/coi/`. Projekty: `app/docs/design/field-extraction.md` i `app/docs/design/generator.md`, razem z tabelami decyzji i listami „Do zrobienia przy implementacji”. Spike'i w `app/spikes/` są punktem wyjścia: przenosisz kod, nie piszesz go od nowa.

## Podział
| Wątek | Obszar (tylko te pliki) |
|---|---|
| Ekstrakcja pól | `coi/extraction/` (`tree.py` z FieldTree, `extract.py`, `postprocess.py`, bramka), `coi/prompts/field_extraction*.md`, `tests/extraction/` |
| Generator | `coi/generator/` (adapter FieldTree → model wewnętrzny, szablony jako dane, layout, UUID, JSONata, `validate.py` z regułami 1–6 i sprawdzaniem odwołań JSONaty), `coi/pipeline.py` (`convert()` zamiast stuba), podpięcie reguł 1–6 pod `POST /api/v1/forms/validate` i `PUT /forms/{id}`, `tests/generator/` |

## Kolejność i kontrakt
1. **Ekstrakcja najpierw commituje `coi/extraction/tree.py`** (FieldTree, w tym `entity_option`, `description_source`, `show_if` z `negate`), a potem wysyła generatorowi wiadomość `ghostex agents send <ref generatora> "..."` z informacją, skąd importować. Ref sprawdzisz w `ghostex orchestrator status`.
2. Publiczne wejście ekstrakcji: `extract(doc: ParsedDocument, on_event=None) -> ExtractionResult(tree, needs_review, trace, cost)`. Drabinka small → large z rundą naprawy, dwuetapowo dla dokumentów długich i wielowariantowych (#9).
3. Generator: `generate(tree, source_sha256, on_event=None) -> (form_json, report_parts, field_map)`. `convert()` składa `parse → extract → generate`, przekazuje zdarzenia do SSE i wypełnia `report` (`trace`, `needs_review`, `proposed_dictionaries`, koszt) oraz `editor.field_map`.
4. Słowniki: generator woła `coi.dictionaries.match(...)` zgodnie z punktem 5 `generator.md`. Jeśli moduł słowników nie jest jeszcze zacommitowany, użyj importu z bezpiecznym fallbackiem (brak dopasowania) oznaczonym `shortcut:`.

## Zasady
- Prompty tylko w `coi/prompts/*.md`. Kod je wczytuje i podstawia zmienne.
- LLM tylko przez `coi/llm.py` (adapter dostawcy, `response_format`). Nie edytuj `coi/llm.py` ani `coi/parsing/`. Brakujące rzeczy opisz w raporcie.
- Konfiguracja (modele, progi, aliasy słowników, `prefill_identity`): jeśli istnieje `coi/config/` (wzór Laravela, robi go wątek backendu), dopisz swój moduł. Jeśli jeszcze nie ma, trzymaj ustawienia w jednym pliku `settings.py` w swoim pakiecie, gotowym do przeniesienia.
- Q31 (checkbox „Klub sportowy” w #9) czeka na decyzję. Zrób go **wymaganym**, przełączanym jedną wartością w ustawieniach.
- W `app/backend/` pracują też wątki parsowania i słowników. Commituj tylko swoje pliki, podając ścieżki (bez `git add -A`). Zmiany w `uv.lock` rób przez `uv add` i nie nadpisuj cudzych. Nie pushuj.

## Dowód
- `uv run pytest tests/<twój obszar>` przechodzi. Testy Eden mają marker `eden`; uruchom je raz i podaj koszt.
- Generator: regresja na #1 i #5 (drzewo z wzorca → JSON → porównanie strukturalne, dopuszczone są tylko różnice opisane w `generator.md`) i walidator reguł 1–6.
- Po wpięciu `convert()`: `POST /api/v1/forms` na #1, #3, #5 i #7 (docx albo pdf) zwraca JSON, który przechodzi `/forms/validate`. Zapisz wyniki w `app/spikes/e2e-out/` (ten katalog ignoruje git) i podaj tabelę: formularz → czas, koszt, liczba pól, `needs_review`.
