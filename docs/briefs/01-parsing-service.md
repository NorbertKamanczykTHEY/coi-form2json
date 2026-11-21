# Brief: backend + serwis parsowania plików

## Cel
Szkielet backendu Flask w `app/backend/` i serwis parsowania: `parse(data: bytes, filename: str) -> ParsedDocument`. Serwis kończy się na `ParsedDocument`. Wyciąganie pól to następny krok i nie należy do tego zadania. Endpointy REST powstaną w osobnym wątku i będą wołać `parse()`.

## Czytaj najpierw
- Spec kontraktu: `/Users/bert/Hacknation/coi_formularze/docs/superpowers/specs/2026-11-21-parser-contract-design.md` (Kind, ParsedDocument, Block, normalizacja `☐` / `___`, `to_markdown`, testy kontraktu).
- Bramka i eskalacja: `/Users/bert/Hacknation/coi_formularze/poc-1-ocr/research/gate-design.md`.
- Szczeble modeli: `/Users/bert/Hacknation/coi_formularze/poc-1-ocr/ladder/ladder.json` oraz `ladder/run.py` (wywołania Eden, krojenie obrazów na kafle, limity tokenów).
- Wyniki PoC: `/Users/bert/Hacknation/coi_formularze/poc-1-ocr/RESULTS.md`, przykład adaptera Kreuzberga w `poc-1-ocr/kreuzberg/`.
- Kontekst zadania: `/Users/bert/Hacknation/coi_formularze/HANDOFF.md`.

## Zmiany względem specu (decyzje użytkownika)
- **PaddleOCR odpada.** Dla skanów i obrazów jest tylko Eden VLM, bez drugiego kontenera.
- **T0 (lokalnie): Kreuzberg z Tesseractem `pol`** dla PDF, DOC/DOCX, ODS i XLSX. Strony skanów PDF też najpierw idą przez Tesseract. Wyżej, gdy bramka odrzuci wynik, wchodzą szczeble VLM z `ladder.json` przez Eden. Tesseract służy też jako „świadek” w bramce po VLM.
- **Szczeble bierzemy teraz z `ladder.json` z PoC.** Trwa benchmark drabinki i jego wynik wejdzie później jako zmiana samego pliku konfiguracji, bez zmian w kodzie. Dlatego drabina musi być w pliku (np. `coi/parsing/ladder.json`), a nie w kodzie.

## Struktura (zaakceptowana)
```
app/backend/
  pyproject.toml        # uv, requires-python >=3.14: flask, kreuzberg, filetype, openai (+ pytest w dev)
  coi/__init__.py       # create_app() – minimalna fabryka Flask, bez endpointów biznesowych
  coi/config.py         # z env: MAX_FILE_MB, LLM_BASE_URL, LLM_API_KEY, LADDER_PATH
  coi/llm.py            # cienki klient OpenAI-compatible (base_url + model z configu)
  coi/parsing/__init__.py   # parse() – jedyne publiczne wejście
  coi/parsing/model.py      # Kind, ParsedDocument, Page, Block (dataclasses + to_dict)
  coi/parsing/detect.py     # rozszerzenie + magic bytes → Kind; wyjątki UnsupportedType, TooLarge
  coi/parsing/normalize.py  # ☐, ___
  coi/parsing/markdown.py   # to_markdown(doc)
  coi/parsing/pipeline.py   # mapa Kind→parsery, fallback, bramka, eskalacja, warnings + trace[]
  coi/parsing/gate.py       # sygnały bez wzorca, wersja minimalna
  coi/parsing/ladder.json
  coi/parsing/parsers/kreuzberg.py
  coi/parsing/parsers/vision.py   # obraz strony → Eden VLM → bloki
  tests/parsing/        # test_detect, test_contract
```
Odchylenia od tej struktury są w porządku, jeśli upraszczają kod. Opisz je w raporcie.

## Ograniczenia
- Python 3.14, uv. Wyłącznie licencje bez copyleftu: żadnego PyMuPDF, Ghostscriptu ani GPL. Pliki trzymamy w pamięci albo w katalogu tymczasowym na czas wywołania.
- Model i endpoint LLM muszą być konfigurowalne (wymóg regulaminu: ten sam model ma się dać podpiąć lokalnie).
- **Klucz Eden** leży w `/Users/bert/Hacknation/coi_formularze/poc-1-ocr/.env`. Nigdy go nie wypisuj, nie wklejaj do plików ani nie commituj. Do `app/backend/.env` (jest w `.gitignore`) skopiuj go poleceniem powłoki, a do repo dodaj `.env.example` bez wartości.
- Format `.JPE` odrzucamy. `.DOC` z docx w środku przyjmujemy jako docx. Wielkość liter w rozszerzeniu nie ma znaczenia.
- Nie ruszaj `poc-1-ocr/`, `materials/` ani `research/`. Pracujesz tylko w `app/`.
- Nie dodawaj endpointów REST ani JWT (to osobny wątek).
- **Każdy moduł (backend, później frontend) ma dać się uruchomić osobno jako kontener Docker.** Dodaj `app/backend/Dockerfile`: oficjalny obraz z jawną wersją (bez `latest`), Alpine, jeśli Kreuzberg i Tesseract `pol` na nim działają, a w przeciwnym razie `slim` z uzasadnieniem w README. Użytkownik bez roota, jeden port, sekrety tylko z env w runtime. Aplikację uruchom serwerem WSGI (np. gunicorn) na `create_app()`. Dodaj też `app/docker-compose.yml` z usługą `backend` (miejsce na `frontend` zostaw na później). Dowód: obraz się buduje, kontener startuje i `parse()` działa w nim na jednym pliku (np. przez `docker run … python -c`). Zależności systemowe i komendy opisz w `app/backend/README.md`.

## Dowód, że działa
- `uv run pytest` przechodzi.
- Testy kontraktu działają na wszystkich formatach formularzy #1 i #7 z `/Users/bert/Hacknation/coi_formularze/materials/` (bez kopiowania plików) i sprawdzają strukturę, znaczniki `☐` / `___` oraz frazy kontrolne z `poc-1-ocr/bench/gold_form*.json`.
- Testy, które wołają Eden, oznacz markerem (np. `@pytest.mark.eden`), żeby dało się je pominąć. Uruchom je raz i podaj koszt.
- Commituj w repo `app/` (git jest już zainicjowany), małymi commitami. Nie pushuj.

## Raport
Tabela: plik × format → ścieżka (T0 / VLM, szczebel), czas, wynik bramki. Do tego koszt Eden, odchylenia od struktury i specu, otwarte pytania.
