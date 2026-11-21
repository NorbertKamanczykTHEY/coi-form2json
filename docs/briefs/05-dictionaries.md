# Brief: słowniki (katalog w SQLite, dane, dopasowanie, edycja przez API)

## Cel
Moduł słowników dla rozszerzeń I („skorzystanie z bazy słowników”) i II („nowy słownik”):
1. **Katalog w SQLite** z danymi: słowniki z materiałów, wypełnione prawdziwymi pozycjami pobranymi z sieci.
2. **Edycja przez endpointy REST** (CRUD słowników i pozycji).
3. **Dopasowanie pola do słownika**: istniejący słownik albo propozycja nowego, według modelu opisanego niżej.

## Czytaj
- `/Users/bert/Hacknation/coi_formularze/research/2026-11-21-flow-review.md`, sekcja 4 „Słowniki” i P4. Tam jest model „istniejący kontra nowy”, reguła „nowy słownik tylko z listą pozycji” i propozycje (DYSCYPLINY_SPORTOWE, RASY_PSOW_AGRESYWNYCH, SPOSOBY_DORECZENIA).
- `/Users/bert/Hacknation/coi_formularze/materials/Materiały do zadania dla Uczestników/Hacknation - Słowniki  (1).docx` (nazwy, struktura, gdzie stosować), „Reguły techniczne…docx” (słowniki tylko w SELECT, RADIO i CHECKBOX, `options: []` przy słowniku, `multiLevelTree`, `searchEnabled`).
- Wzorce #1 i #5 (JSON w `materials/1.*` i `materials/5.*`): `Kraje`, `TERYT_4G_DOWODOWY`, `TERYT_DOWODOWY`.
- `/Users/bert/Hacknation/coi_formularze/app/docs/api-assumptions.md` (A7, `report.proposed_dictionaries`).

## Dane (pobierz z sieci, zapisz jako seed w repo)
- **TERYT** (GUS): województwa, powiaty, gminy (TERC) i miejscowości (SIMC), jako drzewo dla `TERYT_4G_DOWODOWY` i `TERYT_DOWODOWY` oraz osobno Województwo, Powiat, Gmina, Miejscowość. Ustal, czym różnią się te dwa TERYT-y (4 poziomy kontra pełny?), i opisz to.
- **Kraje**: polskie nazwy krajów (ISO 3166).
- **Numery kierunkowe**: krajowe i międzynarodowe.
- Pozycje nowych słowników, jeśli istnieje oficjalna lista (np. rasy psów uznawanych za agresywne z rozporządzenia MSWiA, dyscypliny z #9).
- Pobieranie odbywa się **raz, offline** (skrypt w `app/backend/scripts/`). W runtime nie ma żadnych zewnętrznych wywołań. Zapisz źródło, datę i licencję każdego zbioru. Duże pliki seeda kompresuj (gzip). Gdyby oficjalne źródło wymagało interakcji (formularz ASP.NET), weź rzetelne lustro i opisz to.

## Dopasowanie: istniejący kontra nowy
- Wejście: etykieta pola, opcje (jeśli są), typ i kontekst sekcji. Wyjście: `{dictionaryName | None, score, reason}` albo propozycja nowego słownika `{id, name, structure, items, fields}`.
- Model decyzji pochodzi z flow-review: najpierw istniejący (aliasy etykiet + pokrycie opcji pozycjami słownika), a nowy słownik powstaje tylko wtedy, gdy mamy listę pozycji.
- **Zamiast Jev** (pomysł z wcześniejszej rozmowy, by pytać o obraz „czy to lista / słownik > 70%”) wybierz alternatywę: rapidfuzz na aliasach i pokryciu opcji, embeddingi albo krótkie wywołanie LLM przez `coi/llm.py`. Uzasadnij wybór czasem, kosztem i trafnością na polach z #1–#9, a próg (np. 0,7) wpisz do konfiguracji.
- Funkcja ma być wołana przez generator JSON COI. Wątek „Generator JSON COI – projekt” projektuje teraz swoją część, więc przeczytaj jego chat (`ghostex read-session-chat <ref> --last 3 --format text`, ref sprawdzisz w `ghostex orchestrator status`) i uzgodnij z nim interfejs.

## API (APIFlask, w ramach backendu)
`GET /api/v1/dictionaries` (lista), `GET /api/v1/dictionaries/{name}` (pozycje: drzewo, `?q=` do wyszukiwania, `?parent=` i stronicowanie dla TERYT), `POST`, `PUT`, `DELETE` dla słownika, CRUD pozycji, `POST /api/v1/dictionaries/match` (dopasowanie dla etykiety i opcji, przydatne we froncie i w testach), `POST /api/v1/dictionaries/from-proposal` (przyjęcie propozycji z `report.proposed_dictionaries`). Słowniki z materiałów są chronione przed usunięciem.

## Współpraca z innymi wątkami
- Wątek „REST API i magazyn SQLite” buduje warstwę SQLite i endpointy formularzy w `app/backend/coi/`. **Słowniki przejmujesz ty.** Najpierw przeczytaj jego kod i chat, potem buduj na jego połączeniu z bazą i jego konwencjach (błędy RFC 9457, JWT). Jeśli zrobił już tabelę albo endpointy słowników, rozbuduj je zamiast pisać od nowa.
- Twój obszar to `coi/dictionaries/` (store, seed, matcher, blueprint), `scripts/` i `app/docs/dictionaries.md` (źródła, licencje, struktura tabel, reguły dopasowania). Rejestrację blueprintu w `create_app` dopisz jedną linią.
- Nie edytuj `coi/parsing/` ani `coi/llm.py`.
- Zależności dodawaj przez `uv add`. Commituj tylko swoje pliki, podając ścieżki (bez `git add -A`). Nie pushuj.

## Dowód
`uv run pytest` przechodzi. Testy: seed się ładuje (liczby województw, powiatów i gmin zgadzają się z GUS), CRUD z JWT, wyszukiwanie w TERYT, dopasowanie na polach z #1, #5, #7, #8 i #9 (tabela: pole → wynik → oczekiwany). Raport z tą tabelą i z uzasadnieniem wyboru metody dopasowania.
