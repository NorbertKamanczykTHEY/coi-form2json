# Brief: REST API (APIFlask) + magazyn SQLite

## Cel
Publiczne REST API backendu według `/Users/bert/Hacknation/coi_formularze/app/docs/api-assumptions.md` (zaakceptowane, przeczytaj całość). To jest jedyny punkt wejścia do aplikacji.

## Kontekst
- Backend: `/Users/bert/Hacknation/coi_formularze/app/backend/` (Flask, uv, Python 3.14). Równolegle w tym samym folderze pracuje wątek „Backend i serwis parsowania”. Jego obszar to `coi/parsing/`, `coi/llm.py`, `coi/config.py`, Dockerfile i compose.
- Serwis parsowania udostępnia `coi.parsing.parse(data, filename) -> ParsedDocument` i wyjątki typu pliku i rozmiaru (sprawdź w `coi/parsing/detect.py`, jak się nazywają).
- **Generatora JSON COI i ekstrakcji pól jeszcze nie ma.** API woła jedną funkcję-szew, np. `coi.pipeline.convert(data, filename, on_event) -> Result(form, report, editor)`. Na razie zrób implementację tymczasową: prawdziwe `parse()` plus minimalny poprawny JSON COI (2 strony, MAIN i FINISH, z tytułem z nazwy pliku) i `editor.source` = ParsedDocument. Oznacz to komentarzem `shortcut:`. Generator podepnie się później pod ten sam szew.

## Zakres
- Endpointy A1–A12: `POST /api/v1/forms` (multipart `file`, `?report`, `?editor`, SSE przy `Accept: text/event-stream`), `GET /api/v1/forms`, `GET/PUT /api/v1/forms/{id}`, `POST /api/v1/forms/validate` (na razie JSON Schema z `materials/Materiały do zadania dla Uczestników/importowanyPlikJsonSchemat*.json`, kopia do `coi/`), `GET/POST /api/v1/dictionaries`, `GET /api/v1/info`, `GET /healthz`, Swagger UI pod `/docs`.
- Walidacja wejścia: nazwa pliku (≤ 250 znaków, bez `; : > < / \ | ' * % $`), rozmiar (`MAX_FILE_MB`, także `MAX_CONTENT_LENGTH`), dokładnie jeden plik. Typ i MIME sprawdza `parse()`, ty mapujesz to na 413 i 415. Błędy w formacie RFC 9457.
- JWT: tylko weryfikacja (HS256 z `JWT_SECRET` albo RS256 z `JWT_JWKS_URL`, opcjonalnie iss, aud i leeway). Biblioteka PyJWT (MIT). Skrypt `make-token` do demo.
- SQLite (stdlib `sqlite3`, bez ORM) w `DB_PATH` na wolumenie. Tabele `forms` i `dictionaries`, proste kolumny plus JSON w kolumnie TEXT. **Strukturę bazy opisz w `app/docs/storage.md`** (tabele, kolumny, po co, czego nie zapisujemy: przesłanego pliku). Słowniki z materiałów (`Kraje`, `TERYT_4G_DOWODOWY`, `TERYT_DOWODOWY` oraz Województwo, Powiat, Gmina, Miejscowość, Numery kierunkowe z „Hacknation - Słowniki”) wstaw jako dane startowe.
- Plik przetwarzany wyłącznie w pamięci, a w logach nie ma jego treści ani sekretów.
- Docker: wolumen `data` w `app/docker-compose.yml` dla backendu. Jeśli wątek parsowania jeszcze nie skończył Dockerfile i compose, dopisz tylko to, czego potrzebujesz, nie przepisując jego pracy.
- Opis REST API w `app/backend/README.md` (sekcja API, z przykładami `curl` i odnośnikiem do `/docs`).

## Granice
- Nie edytuj `coi/parsing/` ani `coi/llm.py`. Jeśli czegoś tam potrzebujesz, opisz to w raporcie.
- Zależności dodawaj przez `uv add` (apiflask, pyjwt[crypto]). Jeśli `uv.lock` zmieni się równolegle, zrób rebase swojej zmiany, nie nadpisuj cudzej.
- Commituj tylko swoje pliki, podając ścieżki (`git add <ścieżki>`, nigdy `git add -A`), małymi commitami. Nie pushuj.

## Dowód
- `uv run pytest` przechodzi. Testy obejmują: 401 bez tokena i ze złym tokenem, 400 dla złej nazwy pliku, 413, 415 (`.JPE`, pdf przemianowany na png), 200 dla #1 docx, zdarzenia SSE (co najmniej `stage` i `result`), `?report` i `?editor`, zapis i odczyt `/forms`, PUT z walidacją, tworzenie słownika.
- `docker compose up backend`, a potem `curl` z tokenem z `make-token` na jednym pliku z materiałów zwraca 200.

## Raport
Lista endpointów z kodami, przykładowe zdarzenie SSE, schemat bazy (odnośnik do `storage.md`), co jest stubem w `convert()`, odchylenia od założeń.
