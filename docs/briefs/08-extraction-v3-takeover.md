# Brief: Ekstrakcja pól v3, przejęcie po limicie

Poprzedni wątek „Ekstrakcja pól – implementacja v2” (S0j:P0jqk:G8esn) wyczerpał limit w połowie zadania. Przejmujesz jego pracę. Kontekst przeczytaj w jego czacie:
`ghostex read-session-chat S0j:P0jqk:G8esn --last 15 --format text` (a dla szczegółów `--all --grep '<słowo>'`).

## Stan
W `app/backend/` są jego niezacommitowane zmiany (zobacz je przez `git -C /Users/bert/Hacknation/coi_formularze/app diff`): `coi/extraction/{extract,gate,tree}.py`, `coi/prompts/field_extraction*.md` i 3 pliki testów. Ostatnio robił:
> „Model mistral-large nie przeszedł schematu szkieletu na #8, bo użył powodu spoza listy `dropped` (…). Nieznany powód zamienię na `legal_info`, żeby G11 wymusił naprawę bez utraty całego szczebla.” Potem: „Coerce unknown drop reason; rerun #8”.

## Zadanie 1 (w toku): sekcje stron postępowania na stronie „Dane”
Reguła ogólna od użytkownika: strona „Dane” zawiera wszystkie dane stron postępowania z dokumentu. Ekstrakcja oznacza `Section.party = True` dla danych stron postępowania: rodzaj składającego, współwnioskodawca, współmałżonek, współwłaściciel, adres zamieszkania i adres do korespondencji składającego. Generator (G0qqu, commit `50bfa48`) czyta to przez `getattr(s, 'party', False)`. Osoba trzecia w sprawie (poprzedni właściciel psa, sportowiec) NIE jest stroną i zostaje w przedmiocie (zob. „Role osób” w `/Users/bert/Hacknation/coi_formularze/research/2026-11-21-flow-review.md`). Adres do korespondencji (B.4) nie może wypaść. Podstawa: ADR 0024. Do testu użyj #8 (`materials/8. Deklaracja…/`, PDF s.1–2, część B.1–B.4). Dokończ, przetestuj, uruchom `extract()` na #8 przez Eden, zacommituj.

## Zadanie 2: sygnał „tylko osobiście”
Generator ma już `applicant_self_only` (ADR 0027, commit `627732b`), a frontend przełącznik ze źródłem „z dokumentu: cytat”. Brakuje sygnału z ekstrakcji: FieldTree `applicant_self_only: bool` + `applicant_self_only_src`. Ustawiamy go tylko wtedy, gdy dokument wprost wymaga działania osobiście lub wyklucza pełnomocnika, z cytatem. Uzgodnij nazwy z kodem generatora (`grep -rn self_only app/backend/coi/generator`).

## Zasady
- **Rozwiązania ogólne, wynikające z treści formularza, nigdy pod konkretny numer formularza.** Przykłady w promptach mają być generyczne (ADR 0024).
- Prompty tylko w `coi/prompts/*.md`.
- Nie edytuj `coi/generator/`, `coi/parsing/` ani `coi/llm.py`. Potrzeby opisz w raporcie.
- Testy: `uv run pytest tests/extraction` przechodzi. Testy Eden raz, z podanym kosztem. Regresu na #1, #5 i #9 ma nie być.
- Commituj tylko swoje pliki, podając ścieżki. Nie pushuj.

## Raport
Krótki: co zacommitowane (hashe), wynik na #8 (sekcje `party`, B.4 obecne), regres #1/#5/#9, koszt.
