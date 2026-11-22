# 0017. Baza: SQLite na wolumenie za SQLAlchemy, przełączana przez `DATABASE_URL`
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (T8, R-II) + ZESPÓŁ

## Kontekst
- Wymóg T8: plik tylko w pamięci albo w katalogu tymczasowym na czas żądania. Rozszerzenie R-II: nowy słownik zasila pola, więc potrzebne jest miejsce na jego zapis.
- Nasz wybór: zapisujemy wynik (formularz, raport, słowniki), a edycja przechodzi przez endpointy (`PUT /forms/{id}`, `POST /dictionaries`).
- Wdrożenie produkcyjne zwykle chce innej bazy niż plik SQLite.

## Decyzja
- MVP: SQLite na wolumenie `data`, dostęp przez SQLAlchemy. Na produkcji zmiana bazy to zmiana `DATABASE_URL`, bez zmian w kodzie.
- Przechowujemy formularze wynikowe (JSON COI, raport, `sha256`, `created_by`) i słowniki. **Przesłanego pliku nie zapisujemy.**
- MVP: każdy uwierzytelniony użytkownik widzi wszystko.

## Konsekwencje
- [storage.md](../storage.md) opisuje już SQLAlchemy i `DATABASE_URL` (aktualizacja 2026-11-22); [api-assumptions](../api-assumptions.md) jest dokumentem historycznym.
- Migracji nie ma (`CREATE TABLE IF NOT EXISTS`). Przejście na inną bazę z danymi wymaga narzędzia migracji, którego nie wybrano.
- `editor.source` to tekst z pliku. Dane osobowe w tekście wymagałyby retencji lub wyłączenia zapisu ([storage](../storage.md)).
