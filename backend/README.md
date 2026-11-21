# COI backend

## REST API

Interaktywny opis (Swagger UI): **http://localhost:8000/docs**. Specyfikacja OpenAPI 3.1: `/openapi.json`. Założenia: `app/docs/api-assumptions.md`, baza danych: `app/docs/storage.md`.

Wszystko pod `/api/v1` wymaga nagłówka `Authorization: Bearer <JWT>`. Wyjątki to `/api/v1/info`, `/healthz` i `/docs`. Backend tylko weryfikuje token: HS256 z `JWT_SECRET` albo RS256 z kluczy `JWT_JWKS_URL`. Opcjonalnie sprawdza `JWT_ISSUER`, `JWT_AUDIENCE` i `JWT_LEEWAY_S`. Token musi zawierać `sub` i `exp`.

| Metoda i ścieżka | Co robi | Kody |
|---|---|---|
| `POST /api/v1/forms` | multipart, pole `file`: jeden plik → JSON COI. `?report=true` zwraca `{id, form, report}`, `?editor=true` dokłada `editor`. `Accept: text/event-stream` włącza SSE | 200, 400, 401, 413, 415, 422, 502, 504 |
| `GET /api/v1/forms` | lista zapisanych formularzy (same metadane) | 200, 401 |
| `GET /api/v1/forms/{id}` | jeden formularz, te same `?report` i `?editor` | 200, 401, 404 |
| `PUT /api/v1/forms/{id}` | zapis poprawionego JSON-a po walidacji | 200, 400, 401, 404, 422 |
| `POST /api/v1/forms/validate` | `{valid, errors[{path, message, rule}]}` | 200, 400, 401 |
| `GET /api/v1/info` | wersja, limity, szczeble modeli (bez tokena) | 200 |
| `GET /healthz` | żywotność (bez tokena) | 200 |

Błędy mają format RFC 9457 `application/problem+json`: `{type, title, status, detail, code}`, a dla walidacji dodatkowo `errors`. Kody 413 i 415 pochodzą z `parse()` (rozszerzenie i magic bytes muszą do siebie pasować). Kod 400 oznacza brak pliku, więcej niż jeden plik albo złą nazwę (> 250 znaków albo któryś ze znaków `; : > < / \ | ' * % $`).

Przesłany plik jest tylko w pamięci, na czas żądania. W bazie zostaje wynik, nazwa pliku i jego sha256. W logach nie ma treści pliku, jego nazwy ani tokenów.

### Przykłady

```bash
# token demo (HS256, podpisany JWT_SECRET z app/.env)
TOKEN=$(docker compose exec -T backend python -m coi.make_token jan.kowalski)
# lokalnie: cd backend && uv run python -m coi.make_token

# konwersja: czysty JSON COI (id jest w nagłówku Location)
curl -i -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.docx" http://localhost:8000/api/v1/forms

# z raportem i danymi dla edytora
curl -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.pdf" "http://localhost:8000/api/v1/forms?report=true&editor=true"

# postęp przez SSE
curl -N -H "Authorization: Bearer $TOKEN" -H "Accept: text/event-stream" -F "file=@wniosek.png" http://localhost:8000/api/v1/forms

# historia, odczyt, poprawka, walidacja
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/forms
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/forms/<id>
curl -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @form.json http://localhost:8000/api/v1/forms/<id>
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @form.json http://localhost:8000/api/v1/forms/validate
```

Strumień SSE. `stage`, `escalation` i `warning` mogą pojawić się wiele razy. Na końcu przychodzi `result`: jego `data` to ta sama treść co w zwykłym wywołaniu, a pole SSE `id:` to id formularza. Zamiast `result` może przyjść `error` z treścią problem+json. Błędy po starcie strumienia (np. 415 z `parse()`) przychodzą jako `event: error`, bo status 200 został już wysłany.

```
event: stage
data: {"stage": "parse", "status": "start"}

event: stage
data: {"stage": "parse", "status": "done", "seconds": 0.01, "parser": "kreuzberg"}

event: stage
data: {"stage": "generate", "status": "start"}

event: stage
data: {"stage": "generate", "status": "done"}

id: 12a41a1f-51e5-470e-917b-0d0095c90cd1
event: result
data: {"title": "wniosek1", "tabs": [...], "flow": {...}}
```

### Konfiguracja API
Zmienne opisuje `app/.env.example`: `JWT_SECRET`, `JWT_ALG`, `JWT_JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_LEEWAY_S`, `MAX_FILE_MB`, `MAX_FILENAME_LEN`, `DATABASE_URL` i `LOG_LEVEL`. Bazę wybiera `DATABASE_URL` (URL SQLAlchemy). Domyślnie to `sqlite:////data/coi.sqlite` na wolumenie, a na produkcji np. `postgresql+psycopg://…`, wtedy sterownik trzeba dodać do obrazu. Poza Dockerem ustaw `DATABASE_URL=sqlite:///./data/coi.sqlite`, bo `/data` istnieje tylko w kontenerze. `DB_PATH=<plik>` nadal działa jako alias dla SQLite.

### Testy
`uv run pytest tests/api`: 401, 400, 413, 415, konwersja #1 docx, SSE, `?report` i `?editor`, zapis, odczyt i PUT z walidacją.

## Konfiguracja (`coi.config`)

Cała konfiguracja jest w jednym miejscu, jak `config/` w Laravelu. Pakiet `coi/config/` ma po jednym module na obszar (`app`, `llm`, `parsing`, `dictionaries`; `auth`, `database` i `generator` dopisują ich właściciele). Każdy moduł ma `load() -> dict`, który czyta zmienne środowiskowe z domyślnymi wartościami. Źródłem jest środowisko procesu, a lokalnie braki uzupełnia `app/.env` (`coi/config/env.py`). Odczyt:

```python
from coi.config import config
config("llm.provider")          # jedna wartość
config("parsing")               # cały obszar jako dict
config("x.y", default=None)     # bez KeyError
```

Wartości są czytane przy każdym wywołaniu, więc zmiana env (np. w testach) działa od razu. `Config.load()` to zrzut ustawień potrzebnych `parse()` i dostawcy LLM. Nowy obszar to nowy plik `coi/config/<obszar>.py` z funkcją `load()`, a każda nowa zmienna trafia też do `app/.env.example`.

## Parsowanie plików (`coi.parsing`)

Jedno wejście: `parse(data, filename, cfg=None, on_event=None) -> ParsedDocument` (kontrakt: `docs/superpowers/specs/2026-11-21-parser-contract-design.md` w repo głównym). Wyjątki: `TooLarge` (413), `UnsupportedType` (415), `ParserEnvironmentError` (500, wina serwera, np. brak Tesseracta albo klucza LLM). `ParsingError` z Kreuzberga oznacza zepsuty plik (422). `on_event(event, payload)` dostaje na żywo `escalation` po każdej próbie VLM i `warning` na końcu.

| Wejście | Ścieżka |
|---|---|
| docx, doc, ods, xlsx | Kreuzberg (tekst). Bramka G1/G2, a G3 liczona dla całego dokumentu. Przy porażce tylko ostrzeżenie, bo bez LibreOffice (MPL) nie ma obrazu strony |
| pdf | każda strona osobno: z warstwą tekstu → Kreuzberg. Bez tekstu albo ze śmieciami (G1/G2) → render strony i ścieżka skanu |
| jpg, jpeg, png, skany pdf | T0: Tesseract `pol` (CLI). Gdy bramka odrzuci wynik, wchodzą kolejne szczeble VLM z `coi/parsing/ladder.json`. Każdy wynik VLM sprawdzamy względem Tesseracta jako świadka (M1 kompletność, M3 pokrycie słów, M5 nagłówki wersalikami) |

Każda decyzja trafia do `trace[]` (szczebel, model, sygnały bramki, koszt), a każde obejście do `warnings[]`. Drabina to plik konfiguracyjny: zmiana modeli albo progów nie wymaga zmian w kodzie (`LADDER_PATH` wskazuje inny plik). Prompty leżą w `coi/prompts/*.md`.

Lokalnie potrzebny jest Tesseract z polskim modelem: `brew install tesseract tesseract-lang` albo `apt install tesseract-ocr tesseract-ocr-pol`. Model może też leżeć w dowolnym katalogu wskazanym przez `TESSDATA_PREFIX` (w środowisku albo w `app/.env`). Testy: `uv run pytest tests/parsing -m "not eden"` działa bez sieci. `-m eden` woła Eden i kosztuje około 1 centa.

## Dostawca LLM i tryb offline (air gap)

`LLM_PROVIDER` wybiera adapter z `coi/llm.py`. Oba mówią protokołem OpenAI, a reszta kodu widzi tylko `Provider.chat()`.

| `LLM_PROVIDER` | Adres | Klucz | Drabina |
|---|---|---|---|
| `eden` (domyślnie) | `https://api.edenai.run/v3` | `EDENAI_API_KEY` (albo `LLM_API_KEY`), bez klucza `ParserEnvironmentError` | `coi/parsing/ladder.json` |
| `local` | `LLM_BASE_URL`, domyślnie `http://localhost:11434/v1` (Ollama). vLLM: `http://<host>:8000/v1` | niepotrzebny (`LLM_API_KEY`, jeśli serwer go wymaga) | `coi/parsing/ladder.local.json` (`qwen3-vl:8b`) |

Przy `local` aplikacja nie wysyła nic na zewnątrz. Kreuzberg i Tesseract działają w procesie i w kontenerze, model VLM stoi w sieci wewnętrznej. Klucz Eden nie jest czytany ani wysyłany. Sprawdza to `tests/parsing/test_airgap.py`: lokalny serwer-atrapa dostaje wszystkie wywołania VLM, a jedyny rozwiązywany host to `127.0.0.1`. Przykład z Ollamą w tej samej sieci compose: `LLM_PROVIDER=local`, `LLM_BASE_URL=http://ollama:11434/v1`, a w kontenerze Ollamy `ollama pull qwen3-vl:8b`.

## Docker

```bash
cd app && docker compose up --build        # backend na :8000, sekrety z app/.env (env_file)
docker build -t coi-backend backend/       # sam obraz
docker run --rm --env-file .env -v "$PWD/wniosek.pdf:/in/w.pdf:ro" coi-backend \
  python -c "from coi.parsing import parse; print(parse(open('/in/w.pdf','rb').read(), 'w.pdf').source)"
```

Obraz: oficjalny `python:3.14.10-slim-trixie`, użytkownik `coi` (uid 10001), port 8000, gunicorn (`gthread`, timeout 600 s, bo strona skanu może przejść całą drabinę VLM, i `--no-control-socket`, bo użytkownik nie ma katalogu domowego). Pakiety systemowe: `tesseract-ocr` i `tesseract-ocr-pol` (Apache-2.0).

**Dlaczego slim, a nie Alpine:** Kreuzberg 4.10.4 ma na PyPI tylko wheele `manylinux_2_28` (glibc). Wersji dla musl nie ma: `pip download --only-binary=:all: kreuzberg==4.10.4` na `python:3.14.10-alpine3.24` kończy się „No matching distribution”. Na Alpine trzeba by budować jego rdzeń w Ruście razem z PDFium ze źródeł. Tesseract z polskim modelem jest w Alpine (`tesseract-ocr-data-pol`), więc ograniczeniem jest tylko Kreuzberg. Wydzielenie Kreuzberga do osobnego kontenera na slim nic by nie dało, bo parsowanie to główna praca backendu i i tak potrzebowałby glibc.
