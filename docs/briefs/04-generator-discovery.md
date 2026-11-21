# Brief: generator JSON COI, rozpoznanie i projekt (bez pełnej implementacji)

## Cel
Zaproponować deterministyczny generator: **drzewo pól przedmiotu wniosku + metadane (adresat, dopuszczalne podmioty) → JSON COI** zgodny ze schematem, wzorcami #1/#5 i regułami. Wynik omówimy z użytkownikiem przed implementacją. Wolno zrobić krótki spike (np. odtworzyć stronę „Dane” #1 z szablonu i porównać).

## Czytaj
- `/Users/bert/Hacknation/coi_formularze/HANDOFF.md` (struktura JSON, layout x/y/rows, JSONata, reguły 1–6, wzorzec stron).
- `/Users/bert/Hacknation/coi_formularze/research/2026-11-21-flow-review.md` (S1–S17, U1–U6, decyzje mentorów: required domyślnie, JSONata tylko true/false, #9 jako jeden JSON).
- Materiały w `/Users/bert/Hacknation/coi_formularze/materials/Materiały do zadania dla Uczestników/`: schemat JSON, opis pól, „Reguły techniczne…”, „Standardy i dobre praktyki…”, Słowniki, Dane inicjalne, wizualizacje #1 i #5. Oczekiwane JSON wzorców: w folderach #1 i #5 w `materials/`.
- `/Users/bert/Hacknation/coi_formularze/app/docs/api-assumptions.md` (`POST /forms/validate`, `report.proposed_dictionaries`, `editor.field_map`).

## Pytania do rozstrzygnięcia w raporcie
1. **Wejście generatora**: jakiego drzewa pól potrzebujesz? Uzgodnij je z wątkiem „Ekstrakcja pól (LLM)”, który projektuje drugą stronę tego kontraktu: przeczytaj jego chat (`ghostex read-session-chat <ref> --last 3 --format text`, ref w `ghostex orchestrator status`) i odnieś się do niego.
2. **Szablony**: jak wyciągnąć z wzorców stałe strony („Dane”, „Kontakt i zgody”, FINISH) i warianty podmiotu (S2/S3/S4), żeby były danymi (pliki JSON/YAML), a nie kodem.
3. **Layout i identyfikatory**: reguły y/rows/cols, `questionOrder`, UUID (deterministyczne, np. uuid5 z techName, żeby wynik był powtarzalny?), techName (snake_case, polskie znaki).
4. **JSONata**: generator wyrażeń SHOW / READ_ONLY z odwołaniem do tytułu strony i techName, z negacją.
5. **Słowniki i dane inicjalne** (rozszerzenia I/II): mapowanie etykiet na słowniki i prefill, propozycja nowego słownika.
6. **Walidator końcowy**: JSON Schema + reguły 1–6 + porównanie strukturalne z #1/#5 jako test regresji. Co z rozbieżnościami schemat/wzorce (`repetingSectionGrid`, `validation: {}`, `multiLevelTree`)?
7. **#9 i flow**: jeden formularz z radiem „rodzaj wniosku” i SHOW; czy flow zostaje liniowy?

## Granice
- Pracujesz w `/Users/bert/Hacknation/coi_formularze/app/`. Notatki i spike'i trzymasz w `app/docs/design/generator.md` i `app/spikes/generator/`. Nie ruszaj `app/backend/coi/`.
- Nie commituj; commity robi koordynator.

## Raport
Proponowane wejście generatora, sposób przechowywania szablonów, reguły layoutu i JSONaty, wynik spike'a (diff z #1), rozbieżności i pytania do użytkownika.
