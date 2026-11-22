# COI Formularze: blankiet → JSON e-usługi

> ## Cold start (5 kroków)
>
> 1. **Wymagania:** Docker z Compose v2. Nic więcej (Python i Node są w obrazach).
> 2. `cp .env.example .env`, a w `.env` wpisz:
>    - `EDENAI_API_KEY=` klucz Eden AI,
>    - `JWT_SECRET=` sekret do podpisu tokenów: `openssl rand -hex 32`.
> 3. `./run-them-all.sh`: buduje obrazy, generuje token JWT (7 dni), uruchamia backend i frontend, czeka na healthcheck i wypisuje linki oraz token.
> 4. Otwórz:
>
>    | | |
>    |---|---|
>    | Frontend | http://localhost:8080 |
>    | **Swagger UI** | **http://localhost:8000/docs** |
>    | OpenAPI 3.1 | http://localhost:8000/openapi.json |
>    | Healthcheck | http://localhost:8000/healthz |
>
> 5. **Token do Swaggera** („Authorize”) i curl: skrypt wypisuje go na końcu i zapisuje w `.env` jako `DEMO_API_TOKEN`. Inny token: `docker compose -p app exec -T backend python -m coi.make_token jan.kowalski --hours 24`.
>
> Stop: `docker compose -p app down` (dane zostają; `-v` usuwa bazę).
>
> **Bez tokena też działa:** `POST /api/v1/forms` (konwersja) i `POST /api/v1/forms/validate` przyjmują żądanie bez nagłówka `Authorization` (zapis jako `created_by=anonymous`; token, jeśli jest, musi być poprawny, inaczej 401):
>
> ```bash
> curl -F file=@blankiet.pdf http://localhost:8000/api/v1/forms > formularz.json
> ```
>
> Pozostałe endpointy (lista, edycja, usuwanie, słowniki) wymagają JWT. Na produkcji ustaw `AUTH_PUBLIC_CONVERT=false`: wtedy wszystko wymaga JWT.
>
> **Uwaga, rozwiązanie tymczasowe (do testów):** frontend dostaje ten token z konfiguracji (`/config.js` z nginx, zmienna `DEMO_API_TOKEN`) i nie pyta o logowanie, więc **każdy, kto otworzy stronę, może go odczytać**. Docelowo logowanie przez IdP urzędu (JWKS, [ADR 0015](docs/adr/0015-jwt-tylko-weryfikacja.md)). API przyjmuje każdy poprawny JWT i nie zależy od tokenu frontu.

Usługa REST przyjmuje **jeden plik** z blankietem formularza urzędowego (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) i zwraca **JSON gotowy do importu** w Generatorze Formularzy COI: strony tematyczne, sekcje, pola z walidatorami, słowniki, dane inicjalne i zależności JSONata (`states` SHOW). Frontend pozwala wczytać pliki (także kilka naraz), śledzić postęp, przejrzeć JSON, podgląd e-usługi i raport pól do sprawdzenia.

Przepływ: `parse → extract → generate → validate`. Tekst wyciągamy lokalnie (Kreuzberg, Tesseract), modele LLM/VLM wchodzą tylko tam, gdzie bramka jakości odrzuci tańszy krok. Szczegóły: [docs/architecture.md](docs/architecture.md). Zgodność z treścią zadania: [docs/compliance.md](docs/compliance.md).

| Katalog | Co jest w środku |
|---|---|
| `backend/` | Flask (APIFlask) + gunicorn, Python 3.14, uv. Pakiet `coi/`: `parsing`, `extraction`, `generator`, `dictionaries`, `config`, `prompts` ([backend/README.md](backend/README.md)) |
| `frontend/` | Vite + React + TypeScript + shadcn/ui, serwowany przez nginx ([frontend/README.md](frontend/README.md)) |
| `docs/` | architektura, zgodność, ADR-y, projekty modułów |
| `results/` | wynikowe JSON-y dla formularzy #1–#9 z raportami, koszt i ocena ekspercka |

## Szybki start

Patrz ramka „Cold start” na górze. Ręcznie, bez skryptu: `docker compose up --build -d` (frontend bez tokenu pyta o wklejenie JWT z `docker compose exec backend python -m coi.make_token demo --hours 720`; zostaje w karcie przeglądarki). Zatrzymanie: `docker compose down` (`down -v` usuwa wolumen `data`).

## Budowanie obrazów

| Obraz | Polecenie | Baza | Użytkownik, port |
|---|---|---|---|
| backend | `docker build -t coi-backend backend/` | `python:3.14.10-slim-trixie` (build: `ghcr.io/astral-sh/uv:0.11.9`) | `coi` (uid 10001), 8000 |
| frontend | `docker build -t coi-frontend frontend/` | `node:24.11.1-alpine3.22` → `nginxinc/nginx-unprivileged:1.29.3-alpine3.22` | `nginx` (bez roota), 8080 |

Wersje są przypięte, bez `latest`. Backend stoi na `slim`, nie na Alpine, bo Kreuzberg ma tylko wheele glibc (uzasadnienie: [backend/README.md](backend/README.md#docker)). Token demo nie jest w obrazie frontendu: nginx wystawia go w runtime (zob. [Tokeny](#tokeny-do-demo)).

## Uruchomienie

- **Docker Compose** (zalecane): `docker compose up --build`. Sekrety backend dostaje w runtime z `app/.env` (`env_file`), nigdy w obrazie ([ADR 0011](docs/adr/0011-sekrety-tylko-w-env.md)). Frontend kieruje `/api` do backendu przez `API_UPSTREAM` (domyślnie `http://backend:8000`).
- **Sam backend:** `docker run --rm -p 8000:8000 --env-file .env -v coi-data:/data coi-backend`
- **Bez Dockera:** `cd backend && uv sync && DATABASE_URL=sqlite:///./local.sqlite uv run gunicorn --preload --bind 127.0.0.1:8000 --worker-class gthread --threads 4 --timeout 600 "coi:create_app()"`. Lokalnie potrzebny jest Tesseract z modelem `pol`.
- **Testy:** `cd backend && uv run pytest -m "not eden"` (bez sieci; `-m eden` woła Eden za około 1 cent). Frontend: `npm run build && npm run lint`.

## Konfiguracja

Cała konfiguracja backendu jest w pakiecie `backend/coi/config/` (jeden moduł na obszar, `load()` czyta zmienne środowiskowe z domyślnymi wartościami). Odczyt w kodzie: `config("llm.provider")`. Źródło: zmienne procesu, lokalnie uzupełnione z `app/.env`. Wzór: [.env.example](.env.example).

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `MAX_FILE_MB` | `20` | maksymalny rozmiar pliku (413 powyżej) |
| `MAX_FILENAME_LEN` | `250` | maksymalna długość nazwy pliku (400 powyżej) |
| `AUTH_PUBLIC_CONVERT` | `true` | `POST /forms` i `/forms/validate` działają bez tokena (`created_by=anonymous`); token, jeśli jest, musi być poprawny. Na produkcji `false` (wszystko wymaga JWT) |
| `JWT_ALG` | `HS256` | `HS256` (wspólny sekret) albo `RS256` (klucze IdP z JWKS) |
| `JWT_SECRET` | brak | sekret HS256, co najmniej 32 losowe bajty |
| `JWT_JWKS_URL` | brak | adres JWKS dla `RS256` |
| `JWT_ISSUER` / `JWT_AUDIENCE` | brak | sprawdzane, jeśli ustawione |
| `JWT_LEEWAY_S` | `30` | tolerancja zegara dla `exp` |
| `DATABASE_URL` | `sqlite:////data/coi.sqlite` | URL SQLAlchemy; produkcja np. `postgresql+psycopg://…` (sterownik do dodania). `DB_PATH` to stary alias |
| `LOG_LEVEL` | `INFO` | logi bez treści plików, nazw i tokenów |
| `LLM_PROVIDER` | `eden` | `eden` albo `local` (air gap) |
| `EDENAI_API_KEY` | brak | klucz Eden (sekret); wymagany przy `eden` |
| `LLM_BASE_URL` | Eden: `https://api.edenai.run/v3`, local: `http://localhost:11434/v1` | dowolny endpoint zgodny z OpenAI (vLLM, Ollama) |
| `LLM_API_KEY` | brak | klucz endpointu, gdy go wymaga (przy `eden` zastępuje `EDENAI_API_KEY`) |
| `LLM_TIMEOUT_S` | `90` | limit jednego wywołania (połączenie: 10 s); timeout = nieudany szczebel drabiny |
| `REQUEST_TIMEOUT_S` | `300` | limit całej konwersji: po nim żadne wywołanie LLM nie startuje; najlepsze drzewo idzie z `needs_review`, a bez drzewa `504 llm_timeout` |
| `LADDER_PATH` | `coi/parsing/ladder.json` (local: `ladder.local.json`) | drabina modeli VLM i progi bramki skanów |
| `TESSDATA_PREFIX` | wbudowana ścieżka Tesseracta | katalog z modelem `pol` |
| `EXTRACTION_LADDER` | `mistral/mistral-small-2603,mistral/mistral-large-2512` | szczeble modeli ekstrakcji pól, po przecinku |
| `EXTRACTION_MAX_TOKENS` | `24000` | limit odpowiedzi modelu ekstrakcji |
| `EXTRACTION_TWO_STAGE_BLOCKS` | `150` | od tylu bloków ekstrakcja dwuetapowa (szkielet, potem strony) |
| `EXTRACTION_WORKERS` | `4` | równoległe wywołania stron w etapie drugim |
| `DICT_MATCH_THRESHOLD` | `0.8` | próg dopasowania pola do istniejącego słownika |
| `GENERATOR_PREFILL_IDENTITY` | `MLPZ` | źródło danych „Twoje dane”: `MLPZ` albo `PESEL` |
| Frontend `API_UPSTREAM` | `http://backend:8000` | runtime, szablon nginx |
| Frontend `VITE_BATCH_CONCURRENCY` | `2` | build, ile plików kolejka importu wysyła naraz |

Prompty, drabiny modeli i szablony stron są plikami, nie kodem: [Dostosowanie bez zmiany kodu](docs/architecture.md#dostosowanie-bez-zmiany-kodu).

### Tryb air gap

`LLM_PROVIDER=local` i `LLM_BASE_URL=http://<serwer>:<port>/v1` (Ollama albo vLLM w sieci wewnętrznej). Aplikacja nie wysyła wtedy nic na zewnątrz i nie czyta klucza Eden. Parsowanie (Kreuzberg, Tesseract) zawsze działa w kontenerze. Drabina VLM: `coi/parsing/ladder.local.json` (`qwen3-vl:8b`), ekstrakcja: `EXTRACTION_LADDER` z nazwami modeli lokalnego serwera. Test: `tests/parsing/test_airgap.py` ([ADR 0010](docs/adr/0010-adapter-dostawcy-modeli-i-air-gap.md)).

## REST API

Wszystko pod `/api/v1` wymaga `Authorization: Bearer <JWT>`, poza `/api/v1/info`. Backend tylko weryfikuje token (HS256 albo RS256 z JWKS IdP urzędu), nie ma endpointu logowania; token musi mieć `sub` i `exp` ([ADR 0015](docs/adr/0015-jwt-tylko-weryfikacja.md)). Pełny, generowany z kodu opis: **`/docs`** (Swagger UI).

| Metoda i ścieżka | Co robi | Kody |
|---|---|---|
| `POST /api/v1/forms` | multipart, pole `file`, **jeden** plik → czysty JSON COI (id w `Location`). `?report=true` → `{id, form, report}`, `?editor=true` dokłada `editor`. `Accept: text/event-stream` → SSE | 200, 400, 401, 413, 415, 422, 502, 504 |
| `GET /api/v1/forms` | lista zapisanych formularzy (metadane) | 200, 401 |
| `GET /api/v1/forms/{id}` | jeden formularz, te same `?report` i `?editor` | 200, 401, 404 |
| `PUT /api/v1/forms/{id}` | zapis poprawionego JSON-a (po walidacji) | 200, 400, 401, 404, 422 |
| `POST /api/v1/forms/{id}/regenerate` | odbudowa z zapisanego `FieldTree` z poprawkami edytora, bez LLM | 200, 401, 404, 409 |
| `POST /api/v1/forms/validate` | `{valid, errors[{path, message, rule}]}`: schemat JSON zadania, reguły R1–R6, unikalne `techName`, odwołania JSONata | 200, 400, 401 |
| `GET/POST /api/v1/dictionaries`, `GET/PUT/DELETE /api/v1/dictionaries/{id}`, `…/{id}/items[/{iid}]` | katalog słowników i ich pozycje; słowniki z materiałów są chronione (409) | 200, 201, 204, 401, 404, 409 |
| `POST /api/v1/dictionaries/match` | który słownik pasuje do pola (ta sama funkcja co w generatorze) | 200, 401 |
| `POST /api/v1/dictionaries/from-proposal` | przyjęcie propozycji z `report.proposed_dictionaries` | 201, 401, 409 |
| `GET /api/v1/info` | wersja, limity, szczeble modeli (bez tokena) | 200 |
| `GET /healthz` | żywotność (bez tokena) | 200 |

W drzewie roboczym są też (jeszcze niezacommitowane) `DELETE /api/v1/forms/{id}` i `PUT /api/v1/forms/{id}/resolved`.

**Walidacja pliku:** rozszerzenie z listy i typ z magic bytes muszą się zgadzać (415). Nazwa: 1–250 znaków, bez `; : > < / \ | ' * % $` (400). Rozmiar ponad `MAX_FILE_MB` → 413. Plik jest tylko w pamięci na czas żądania; w bazie zostaje wynik, nazwa i sha256 pliku ([storage.md](docs/storage.md)).

**Błędy:** RFC 9457 `application/problem+json` `{type, title, status, detail, code}`, przy walidacji także `errors` ([ADR 0016](docs/adr/0016-bledy-rfc-9457-openapi-batch-we-froncie.md)).

**SSE** ([ADR 0014](docs/adr/0014-postep-przez-sse.md)): zdarzenia `stage` (`parse`, `extract`, `generate`: `start`/`done`), `escalation` (kolejny szczebel modelu), `warning`, na końcu `result` (ta sama treść co bez SSE, pole `id:` to id formularza) albo `error` (problem+json).

### Przykłady

```bash
TOKEN=$(docker compose exec -T backend python -m coi.make_token jan.kowalski)

curl -s http://localhost:8000/healthz
curl -i -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.docx" http://localhost:8000/api/v1/forms
curl -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.pdf" "http://localhost:8000/api/v1/forms?report=true&editor=true"
curl -N -H "Authorization: Bearer $TOKEN" -H "Accept: text/event-stream" -F "file=@skan.png" http://localhost:8000/api/v1/forms
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @form.json http://localhost:8000/api/v1/forms/validate
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/dictionaries
```

Nazwę z `;` w `curl -F` trzeba ująć w cudzysłów (`filename="a;b.docx"`), inaczej curl utnie ją sam.

## Tokeny do demo

`python -m coi.make_token <sub> [--hours N]` podpisuje token HS256 sekretem `JWT_SECRET` (z `JWT_ISSUER`/`JWT_AUDIENCE`, jeśli ustawione).

```bash
docker compose exec -T backend python -m coi.make_token jan.kowalski          # w kontenerze
cd backend && uv run python -m coi.make_token demo-frontend --hours 720       # lokalnie
```

**Tymczasowo, do testów (`shortcut:` w kodzie, ADR 0015 dopisek):** `run-them-all.sh` przy każdym starcie generuje token (7 dni), zapisuje go w `.env` (`DEMO_API_TOKEN`, informacyjnie, do curl i Swaggera) i w env kontenera frontu. nginx serwuje go jako `/config.js`, a front nie pokazuje pola „Token”. Bez tokenu w konfiguracji (np. `docker compose up` bez skryptu) zostaje wklejanie. Token nie trafia do obrazu ani do bundla, ale każdy, kto otworzy stronę, może go odczytać. Backend nie zależy od tego mechanizmu: przyjmuje każdy poprawny JWT (Swagger, curl, inni klienci). Na produkcji token przychodzi z logowania w IdP urzędu (`JWT_ALG=RS256`, `JWT_JWKS_URL`), a `/config.js` znika.

## Dokumentacja

| Dokument | Treść |
|---|---|
| [docs/architecture.md](docs/architecture.md) | architektura, przepływ, bramki, kontrakty, bezpieczeństwo, koszt |
| [docs/compliance.md](docs/compliance.md) | wymagania zadania odhaczone z dowodami, luki |
| [docs/requirements.md](docs/requirements.md) | wymagania z treści zadania (ID M*, R-*, T*) |
| [docs/adr/](docs/adr/README.md) | decyzje architektoniczne 0001–0027 |
| [docs/flow-scenarios.md](docs/flow-scenarios.md) | scenariusze S1–S17, role osób, decyzje mentorów |
| [docs/design/](docs/design/) | kontrakt parsera, ekstrakcja pól, generator |
| [docs/dictionaries.md](docs/dictionaries.md), [docs/storage.md](docs/storage.md) | słowniki, baza danych |
| [results/README.md](results/README.md) | wyniki E2E, koszt, ocena ekspercka |
