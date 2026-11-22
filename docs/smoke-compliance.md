# Smoke zgodności technicznej (pkt 5 zadania, T1–T12)

Sprawdzone w praktyce na działającym stosie, 2026-11-22. Wersja: HEAD `63caa8a` (drzewo czyste, `diff -rq` obrazu z `backend/coi` bez różnic). Stos: `docker compose -p coismoke` (porty 18000/18080, własny wolumen, `MAX_FILE_MB=1`, potem zmieniany na 3 i 100 przez env bez przebudowy), po teście `down -v`. Stos demo (`app`, 8000/8080) nie był dotykany.

Źródła wymagań: `materials/COI - Pełna treść zadania konkursowego.pdf` pkt 5, [requirements.md](requirements.md) (T1–T12), [../README.md](../README.md), [compliance.md](compliance.md). Zakres: tylko techniczne wymagania z pkt 5 oraz twierdzenia README i compliance.md o nich. Testy jednostkowe (`261 passed`) i jakość wyniku LLM poza zakresem.

Skrót: **PASS** spełnione, **FAIL** niespełnione, **PASS\*** spełnione, ale z rozbieżnością w dokumentacji (sekcja niżej). Narzędzia: Python `http.client` z ręcznie składanym multipartem (surowe nagłówki), `curl`, `docker exec/inspect/history/diff`. `T` = token `good` z `make_token` (HS256, `JWT_SECRET` stosu).

## Wynik

| Wymaganie | Test | Wynik | Dowód |
|---|---|---|---|
| **T5** formaty przyjmowane | Prawdziwy plik #3 w 8 formatach, `POST /api/v1/forms?report=true` | PASS | `.pdf .doc .docx .ods .xlsx .jpg .jpeg .png` → 8× 200 (4–32 s) |
| T5 wielkość liter rozszerzenia | Te same pliki jako `….PDF .DOC .DOCX .ODS .XLSX .JPG .JPEG .PNG` | PASS | 8× 200 |
| T5 inne formaty odrzucane | `.txt .exe .gif .odt .xls .zip .json`, brak rozszerzenia, `a.pdf.exe` | PASS | wszystkie 415 `extension .X not allowed` |
| T5 MIME zgodny z rozszerzeniem | PDF jako `.docx`, PNG jako `.jpg`, JPEG jako `.png`, DOCX jako `.xlsx`, XLSX jako `.ods`, PNG jako `.pdf`, tekst/pusty jako `.pdf` | PASS | wszystkie 415 `content (application/pdf) does not match .docx` itd. |
| T5 nagłówek `Content-Type` części multipart | `application/octet-stream` przy poprawnej treści | PASS | 200; decyduje treść (magic bytes), nie deklaracja klienta |
| **T6** długość nazwy | 249, 250 znaków (ASCII i `ą`), 251, 300, pusta | PASS | 249/250 → przechodzi (dalej 415 z treści), 251/300/pusta → 400 `invalid_filename`; 250× `ą` (496 B UTF‑8) przechodzi, 251× → 400: liczone znaki, nie bajty |
| T6 znaki `; : > < / \| ' * % $` osobno (`a<c>b.pdf`) | `;` `:` `>` `<` `/` `\|` `'` `*` `%` `$` | PASS | 10/10 → 400 `invalid_filename` (z `\` zob. FAIL niżej) |
| T6 **znak `\`** | surowy nagłówek `filename="a\b.pdf"` (tak wysyła przeglądarka) | **FAIL** | 415 (nazwa przeszła, `\` znika); dopiero `filename="a\\b.pdf"` (z escape) → 400. Zob. F1 |
| T6 kontrola fałszywych odrzuceń | `- _ spację ( ) & # @ ! + = , ą` | PASS | żaden nie daje 400 |
| T6 nazwa z polskimi znakami i spacjami | `Wniosek o wydanie zaświadczenia.docx` | PASS | 200 |
| **T7** `MAX_FILE_MB` tuż poniżej / równo / powyżej | `MAX_FILE_MB=1`, PNG dopełniony zerami: 1 MiB−1, 1 MiB, 1 MiB+1, +60 kB, +200 kB, +6 MiB; bezpośrednio :18000 i przez front :18080 | PASS | −1 i równo → 200 (pełna konwersja); +1 B, +60 kB → 413 `File is larger than 1.0 MB`; +200 kB → 413 `Request Entity Too Large` (Werkzeug `MAX_CONTENT_LENGTH`); +6 MiB → 413 (curl) |
| T7 zmiana bez przebudowy | `SMOKE_MAX_MB=3 docker compose up -d --no-build` | PASS | ID obrazu przed/po identyczne (`sha256:2fefab97…`); `GET /api/v1/info` → `max_file_mb: 3.0`; 1 MiB+1 → 200, 3 MiB → 200, 3 MiB+1 → 413 |
| T7/T11 `MAX_FILENAME_LEN` z env | `MAX_FILENAME_LEN=20` | PASS | nazwa 20 znaków przechodzi, 21 → 400 `1-20 characters` |
| T7 limit przez nginx frontendu | `MAX_FILE_MB=100`, plik 55 MiB przez :18000 i :18080 | **FAIL** | :18000 → 415 (limit przeszedł), :18080 → 413 HTML nginx. Zob. F2 |
| **T4** dokładnie jeden plik | 0 plików (pusty multipart, brak body, JSON), 2× pole `file`, `file`+`file2`, 3 pliki, jeden plik w polu `doc` | PASS | wszystkie 400 `bad_request` |
| **T11** JWT: brak / zły / wygasły → 401 | brak nagłówka, `Bearer ` puste, śmieci, `Basic`, zły sekret, wygasły 1 h temu, `alg=none`, bez `sub`, bez `exp`, HS512 | PASS | 10/10 → 401 (`WWW-Authenticate: Bearer …`); poprawny token → przechodzi (415 z treści) |
| T11 JWT: tolerancja `exp` | `exp` = teraz−10 s i teraz−60 s przy `JWT_LEEWAY_S=30` | PASS | −10 s → przyjęty, −60 s → 401 |
| T11 JWT: parametry z env | `JWT_ISSUER=coi-smoke`, `JWT_LEEWAY_S=0` | PASS | bez `iss` → 401 `missing "iss"`, `iss=other` → 401 `Invalid issuer`, `iss` ok → przyjęty, `exp` teraz−5 s → 401 |
| T11 JWT: brak sekretu (fail closed) | kontener bez `JWT_SECRET`; `JWT_ALG=RS256` bez `JWT_JWKS_URL` | PASS | 401 w obu; kontrola z sekretem → 200 |
| T11 JWT na wszystkich trasach | 14 ścieżek z `/openapi.json`, bez tokena i z wygasłym | PASS | wszystkie `/api/v1/*` → 401, publiczne: `/api/v1/info`, `/healthz`, `/health`, `/docs`, `/openapi.json` (zgodnie z README) |
| **T8** upload nie ląduje na dysku backendu | plik 700 kB (> 500 kB próg Werkzeug) z unikalnym markerem, odpytywanie `/tmp /var/tmp /dev/shm /data /app` co 0,2 s w trakcie żądania | PASS | upload nie pojawia się w `/tmp`; w trakcie tylko `/tmp/tmp*/page.png, out.txt, out.tsv` (Tesseract, katalog tymczasowy żądania) i puste pliki heartbeat `wgunicorn-*` |
| T8 po żądaniu | `docker diff` przed/po, `find /tmp /var/tmp /dev/shm -type f`, `grep -rla MARKER /` w obu kontenerach | PASS | `docker diff` bez zmian względem stanu sprzed uploadu; w `/tmp` backendu pusto; marker nigdzie (0 trafień) |
| T8 baza | `sqlite3` `/data/coi.sqlite` (tabele, kolumny, grep markera) | PASS | tabele `forms`, `dictionaries`, `dictionary_items`; w `forms` wynik JSON, `filename`, `sha256`, `report`, `editor`; marker 0 trafień, bajtów pliku brak (ale zob. R5) |
| T8 front (nginx) | polling `/tmp` frontendu podczas uploadu przez :18080 | PASS\* | nginx buforuje body do `/tmp/client_temp/0000000002 (deleted)` na czas żądania, po żądaniu pusto. Dozwolone ("przestrzeń tymczasowa"), ale README mówi "tylko w pamięci" (R4) |
| T8 logi | `docker logs` backend i front: marker, nazwa, `eyJ`, `Bearer`, sekrety | PASS | 0 trafień; log `convert sha256=… size=… user=…` |
| **T9/T10** wersje jawne, bez `latest` | `FROM` w Dockerfile, `grep latest` w Dockerfile i compose | PASS | `python:3.14.10-slim-trixie`, `ghcr.io/astral-sh/uv:0.11.9`, `node:24.11.1-alpine3.22`, `nginxinc/nginx-unprivileged:1.29.3-alpine3.22`; `latest` nie występuje |
| T10 obrazy oficjalne | pochodzenie baz | PASS\* | `python`, `node` to Docker Official Images; `nginxinc/nginx-unprivileged` (wydawca NGINX) i `ghcr.io/astral-sh/uv` (build‑only, wydawca Astral) nie są "Docker Official Image" (R7) |
| T10 lekkie (Alpine) | `/etc/os-release` w kontenerach | PASS\* | front Alpine 3.22; backend Debian 13 `slim` (świadome odstępstwo, uzasadnione w README, wymóg to "preferować") |
| T10 proces nie‑root | `docker image inspect` + `/proc/*/status` w kontenerach | PASS | backend `User=coi`, wszystkie procesy `uid=10001`; front `User=101`, master i workery `uid=101` |
| T10 tylko potrzebne porty | `EXPOSE`, `docker ps` | PASS | backend 8000, front 8080, nic więcej |
| T10 brak sekretów w obrazach | wartości `EDENAI_API_KEY`, `JWT_SECRET` z `app/.env` i sekret stosu: `docker history --no-trunc`, `ENV` obrazu, `grep -rlaF /` w obu obrazach, pliki `.env*`, `eyJ…eyJ` | PASS | 0 trafień; `ENV` obrazów bez zmiennych `KEY/SECRET/TOKEN/PASS`; `.env*` i `*.pem` tylko certyfikaty CA |
| T10 bundle frontu | `grep` w `/usr/share/nginx/html` | PASS | tylko kod `Authorization: Bearer ${token z sessionStorage}`; brak tokenu, sekretu, kluczy, sourcemap |
| T10 sekrety tylko w runtime | `env_file: .env` w compose, brak `ARG`/`ENV` sekretów | PASS | klucz widoczny wyłącznie w środowisku działającego kontenera |
| T9 healthchecki | `docker inspect` stanu, ręcznie komendy z compose na dobrym i złym porcie | PASS\* | oba `healthy`, `FailingStreak=0`; komenda backendu na złym porcie `exit=1`, frontu `exit=1`; `depends_on: service_healthy` działa (front startuje po backendzie). Healthchecki tylko w compose, nie w Dockerfile (R8) |
| T11 konfiguracja README ↔ kod | porównanie zmiennych czytanych przez kod z tabelą README i `.env.example` oraz domyślnych wartości (13 sprawdzonych) | FAIL | 12/13 domyślnych zgodne; `EXTRACTION_WORKERS` 6 w kodzie vs 4. Brakujące zmienne: zob. R1–R3 |
| T12 README: budowanie | `docker build -t coi-backend backend/`, `docker build -t coi-frontend frontend/` (polecenia z README) | PASS | oba budują się, `User=coi` / `101` (tagi usunięte po teście) |
| T12 README: uruchomienie | `docker compose up -d` wg README (zmieniony tylko plik compose, własny projekt) + `make_token` w kontenerze | PASS | stos wstaje, token generuje się (`docker compose exec -T backend python -m coi.make_token`); `./run-them-all.sh` nie uruchamiany (kolidowałby z demem na 8000/8080), przeczytany: logika poprawna |
| T12 README: opis API | `GET /openapi.json`, 14 ścieżek, `info`, SSE | PASS | OpenAPI `3.1.0` zgodnie z README; zdarzenia SSE `stage`×6, `escalation`, `result` zgodnie z opisem; kody 400/401/413/415 zgodne z tabelą |
| **Pełna konwersja** #3 docx | `POST /api/v1/forms?report=true` z `Wniosek o wydanie zaświadczenia.docx` → `POST /api/v1/forms/validate` na wyniku | PASS | 200 w 4,8 s; `validate` → `{"valid": true, "errors": []}`; to samo dla wyników z pozostałych formatów (8× `valid: true`, warianty z rozszerzeniem wielkimi literami); zapisany wynik z `GET /forms/{id}` też `valid: true` |
| Kontrola ujemna validate | `POST /forms/validate` z `{"title":1}` | PASS | `valid: false`, 1 błąd |

## Lista FAIL

- **F1. Znak `\` w nazwie pliku nie jest odrzucany.** Kod (`api.py:136`) sprawdza `\`, ale Werkzeug przy parsowaniu `Content-Disposition` usuwa pojedynczy surowy backslash (`filename="a\b.pdf"` → `ab.pdf`), więc kontrola go nie widzi. Przeglądarki wysyłają backslash surowo. Odrzucone są tylko nazwy z `\\` (escape) lub ścieżkami typu `C:\x`, `\\srv\x`. Efekt: wymaganie T6 niespełnione dla typowego klienta. Nie testowano w prawdziwej przeglądarce, tylko surowym multipartem i `curl -F` (ten też daje 415, czyli nazwa przechodzi).
- **F2. Limit nginx 50 MB na sztywno.** `frontend/nginx/default.conf.template`: `client_max_body_size 50m` niezależnie od `MAX_FILE_MB`. Przy `MAX_FILE_MB` > 50 przez front plik > 50 MB dostaje HTML-owe 413 nginx (bez `problem+json`), bezpośrednio do backendu przechodzi. Domyślne 20 MB nieszkodliwe.
- **F3. Dokumentacja konfiguracji rozjeżdża się z kodem** (R1–R3 niżej): zmienne w kodzie bez wpisu w README i `.env.example` oraz inny domyślny `EXTRACTION_WORKERS`.

## Rozbieżności z dokumentacją

| # | Gdzie | Treść dokumentacji | Stan faktyczny |
|---|---|---|---|
| R1 | `README.md` tabela, `.env.example:41` | `EXTRACTION_WORKERS` domyślnie `4` | kod `backend/coi/config/extraction.py:12`: `"6"` |
| R2 | `README.md` tabela konfiguracji | brak `EXTRACTION_PARALLEL_RUNGS` (domyślnie włączone), `EXTRACTION_REPAIR_BUDGET_S` (20), `RENDER_FONT`, `TERYT_DOWODOWY`, `TERYT_4G_DOWODOWY`, `ENV_FILE` | czytane w `config/extraction.py`, `config/parsing.py`, `config/dictionaries.py`, `config/__init__.py` |
| R3 | `.env.example` | brak `EXTRACTION_PARALLEL_RUNGS`, `EXTRACTION_REPAIR_BUDGET_S`, `TERYT_*`, `ENV_FILE` (`RENDER_FONT` jest) | zmienne czytane przez kod |
| R4 | `README.md:112`, `docs/storage.md:33` | "Plik jest tylko w pamięci na czas żądania" | upload w RAM w backendzie, ale: nginx frontendu buforuje body w `/tmp/client_temp` (usuwane po żądaniu), a Tesseract zapisuje `page.png` w `/tmp/tmp*` (usuwane po żądaniu). Zgodne z T8 ("pamięć lub przestrzeń tymczasowa"), nieprecyzyjne w opisie |
| R5 | `README.md:112` | "w bazie zostaje wynik, nazwa i sha256 pliku" | w tabeli `forms` jest też `report` i `editor` (`editor.source` = tekst wyciągnięty z pliku, opisane w `docs/storage.md:37`, ale nie w README) |
| R6 | `README.md:45`, `README.md:142`, `docs/compliance.md:57` (T10) | "Frontend wbudowuje token demo z `frontend/.env` przy buildzie", "Token frontendu trafia do bundla JS", "token demo frontendu wbudowany w bundle" | nieaktualne: bundle bez tokenu, `.env` w `frontend/.dockerignore`, `frontend/.env.example` i `frontend/README.md:14` mówią, że nic nie jest wbudowane (ADR 0015); README i compliance.md są sprzeczne z frontend/README.md |
| R7 | `docs/compliance.md:57`, `README.md:44` | wymienia `nginxinc/nginx-unprivileged` jako nie‑Docker‑Official | zgodne; niewymieniony `ghcr.io/astral-sh/uv` (build‑only, wydawca Astral, też nie Docker Official) |
| R8 | `README.md` ("czeka na healthcheck"), `docs/compliance.md` | healthchecki jako cecha stosu | są tylko w `docker-compose.yml`; `docker run` samego obrazu nie ma `HEALTHCHECK` (`Config.Healthcheck=nil`). Front sprawdza tylko `/` nginx, nie łączność z backendem |
| R9 | `README.md` tabela API | "Wszystko pod `/api/v1` wymaga tokena, poza `/api/v1/info`" | zgodne (potwierdzone na 14 trasach); w tabeli brakuje aliasu `GET /health` (działa, 200) |

## Status napraw (2026-11-22)

- **F1 naprawione.** `coi/api.py` sprawdza też surowy nagłówek `Content-Disposition` (`FileStorage.headers`); `filename="a\b.pdf"` → 400 `invalid_filename`. Test: `test_400_raw_backslash_in_filename`.
- **F2 naprawione.** `client_max_body_size` w nginx wynika z `MAX_FILE_MB` (+1 MB) w runtime (`frontend/nginx/15-max-body.envsh`, zmienna `MAX_FILE_MB` kontenera frontu, w compose z `.env`); 413 z nginx ma postać `application/problem+json` z `code: file_too_large`.
- **F3 / R1–R3 naprawione.** `EXTRACTION_WORKERS=6`; dopisane `EXTRACTION_PARALLEL_RUNGS`, `EXTRACTION_REPAIR_BUDGET_S`, `RENDER_FONT` (README) i zmienne frontu `MAX_FILE_MB`, `DEMO_API_TOKEN`. Lista zmiennych z kodu `coi/config` i `coi/__init__.py` sprawdzona skryptem. `TERYT_DOWODOWY`, `TERYT_4G_DOWODOWY` to nazwy słowników, a `ENV_FILE` stała w kodzie, nie zmienne środowiskowe, więc nie trafiają do tabeli.
- **R4, R5 naprawione.** README, `docs/storage.md` i `docs/compliance.md` (T8): backend trzyma plik w RAM; bufor nginx i pliki tymczasowe Tesseracta są kasowane po żądaniu; w bazie zostają wynik, `report`, `editor` (z `editor.source`), nazwa i sha256.
- **R6 naprawione.** README i compliance.md opisują token demo wstrzykiwany w runtime (`/config.js`), tymczasowo, do testów (ADR 0015, dopisek).
- **R7, R8, R9 naprawione.** compliance.md (T10, P3) wymienia `ghcr.io/astral-sh/uv` i zakres healthchecków; README ma alias `GET /health`.

## Obserwacje poza wymaganiami

- Przy tym samym pliku `.docx` (#3) jeden z 16 przebiegów zwrócił inny `title` ("…o użytkach rolnych i gospodarstwie rolnym"), reszta "Wniosek o wydanie zaświadczenia": zmienność modelu, wynik nadal `valid: true`.
- Kontenery bez `read_only`, `cap_drop`, `no-new-privileges` (nie wymagane w zadaniu; użytkownik nie‑root i brak `privileged` są).
- `GET /api/v1/info` (bez tokena) ujawnia szczeble modeli LLM i limity; zgodne z README, ale warto o tym wiedzieć.
- Python `http.client` przy wysłaniu 6 MiB bezpośrednio do backendu dostał `Broken pipe` zamiast 413 (serwer zamyka połączenie przed końcem body); `curl` dostaje poprawne 413.
