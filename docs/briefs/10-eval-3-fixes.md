# Brief: poprawki po EVAL-3 (reguły ogólne G1–G17)

Źródło: `/Users/bert/Hacknation/coi_formularze/app/results/eval-3/README.md` (tabela reguł) i pliki `<n>.md` z dowodami. Każda reguła wynika z treści formularza. **Wolno wdrażać tylko reguły ogólne, nigdy warunki pod konkretny numer formularza. Przykłady w promptach mają być generyczne (ADR 0024).**

## Podział
| Wątek | Reguły |
|---|---|
| Ekstrakcja (prompt, bramka, postprocess; `coi/extraction/`, `coi/prompts/`) | G1 (prompt + bramka), G2, G3 (prompt), G4, G6 (prompt), G7, G8 (prompt), G12 (prompt), G13, G17 (bramka) |
| Generator (`coi/generator/`, szablony, walidator) | G5, G9, G10, G11, G14, G15, G16, oraz części generatora z G1 (po obcięciu warunku nie zostawiać REQ na obu gałęziach), G3 (deduplikacja uploaderów, usuwanie pełnomocnictwa), G6, G8 (TEXT_BLOCK „Opłata” na stronie kontaktu), G12 (podział sekcji i stron) |

Kolejność w każdym wątku: najpierw reguły z rozbieżnościami krytycznymi (K), potem średnimi.

## Kontrakt między wątkami
Jeśli reguła wymaga nowego pola w FieldTree (np. wariant wnioskodawcy dla G5, opłata za sprawę dla G8), ekstrakcja dodaje je w `coi/extraction/tree.py`, commituje i informuje generator (`ghostex agents send <ref> "..."`, refy w `ghostex orchestrator status`). Generator czyta nowe pola przez `getattr` z wartością domyślną.

## Zasady
- Nie edytuj obszaru drugiego wątku, `coi/parsing/` ani `coi/llm.py`.
- `uv run pytest -m "not eden"` przechodzi. Każda reguła ma test jednostkowy na generycznym przykładzie.
- Eden: na koniec jeden przebieg na formularzach, których dotyczą twoje reguły, przez `PYTHONPATH=. uv run python ../results/run.py` (z `app/backend`), bez nadpisywania `app/results/` (zapis do `app/spikes/e2e-out/`). Podaj koszt i dla każdej reguły, czy rozbieżność z `eval-3/<n>.md` zniknęła.
- Commituj tylko swoje pliki, podając ścieżki. Nie pushuj.

## Raport
Tabela: reguła → commit → test → efekt na formularzach (zniknęła / częściowo / nie). Regresy. Koszt.
