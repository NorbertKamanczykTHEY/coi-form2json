# Brief: ekstrakcja pól, rozpoznanie i projekt (bez pełnej implementacji)

## Cel
Zaproponować, jak z `ParsedDocument` (wynik serwisu parsowania) zrobić **drzewo pól przedmiotu wniosku**: strony merytoryczne → sekcje → pola {label, typ, opcje, wymagalność, zależności, powtarzalność, rola osoby, słownik, walidator}. Wynik omówimy z użytkownikiem przed implementacją. Wolno robić krótkie eksperymenty (spike), ale nie budujemy jeszcze modułu produkcyjnego.

## Czytaj
- `/Users/bert/Hacknation/coi_formularze/research/2026-11-21-flow-review.md` (scenariusze S1–S17, reguły R1–R7, odpowiedzi mentorów). To główne źródło.
- `/Users/bert/Hacknation/coi_formularze/HANDOFF.md`, `/Users/bert/Hacknation/coi_formularze/app/docs/api-assumptions.md` (pole `editor.field_map`: każde pole musi wskazywać miejsce w źródle).
- Kontrakt wejścia: `/Users/bert/Hacknation/coi_formularze/docs/superpowers/specs/2026-11-21-parser-contract-design.md`, kod w `/Users/bert/Hacknation/coi_formularze/app/backend/coi/parsing/` (powstaje równolegle w innym wątku; tylko czytaj).
- PoC drabinki: `/Users/bert/Hacknation/coi_formularze/poc-1-ocr/ladder/` (prompt „tekst → pola”, wyniki modeli Eden).
- Materiały: `/Users/bert/Hacknation/coi_formularze/materials/` (wzorce #1 i #5 z oczekiwanym JSON; formularze #2, #3, #4, #7, #8, #9).

## Pytania do rozstrzygnięcia w raporcie
1. **Model drzewa pól**: schemat (Pydantic albo dataclasses, JSON Schema dla structured output). Uzgodnij go z wątkiem „Generator JSON COI”, który projektuje drugą stronę tego samego kontraktu: przeczytaj jego chat (`ghostex read-session-chat <ref generatora> --last 3 --format text`, ref sprawdzisz przez `ghostex orchestrator status`) i odnieś się do niego w raporcie.
2. **Co robi LLM, a co kod**: klasyfikacja bloków (szablon kontra przedmiot wniosku), typy pól, opcje, zależności „inne → pole”, sekcje powtarzalne, rola osoby, podział na strony. Co da się zrobić regułami i presetami (PESEL, adres, kontakt, załącznik)?
3. **Prompt i liczba wywołań**: jedno wywołanie na dokument czy kilka etapów? Długie dokumenty (#9 ma 16 stron)?
4. **Bramka jakości** dla wyniku LLM bez wzorca: zgodność ze schematem, pokrycie etykiet względem tekstu źródłowego, `needs_review`.
5. **Model z Eden**: który zaczyna, jaka eskalacja, koszt i czas na #1, #5, #3 i #7 (spike na 2–4 formularzach, koszt poniżej $1).

## Granice
- Pracujesz w `/Users/bert/Hacknation/coi_formularze/app/`. Notatki i spike'i trzymasz w `app/docs/design/field-extraction.md` i `app/spikes/field-extraction/`. Nie ruszaj `app/backend/coi/`.
- Klucz Eden jest w `app/.env` (`EDENAI_API_KEY`). Nie wypisuj go.
- Nie commituj; commity robi koordynator.

## Raport
Proponowany model drzewa (fragment), podział LLM / kod, wyniki spike'a (tabela: formularz → recall pól, typy, czas, koszt), ryzyka i pytania do użytkownika.
