# Zgodność z treścią zadania

Stan na HEAD `1d9ff53` (2026-11-22), sprawdzany w kodzie i na działającym obrazie, nie w dokumentach. Wymagania i ich ID: [requirements.md](requirements.md) (z `materials/COI - Pełna treść zadania konkursowego.pdf`, pkt 3.2, 3.3, 4, 5, 6, 8).

Stan: ✅ spełnione · 🟡 częściowo · ❌ brak.

## Weryfikacja

- `cd backend && uv run pytest -m "not eden"`: **261 passed**, 7 pominiętych (wywołania Eden), 28 s.
- `docker compose up --build` (osobny projekt, porty 18000/18080): `/healthz` 200, front 200, `/docs` 200, `/api/v1/forms` bez tokena 401, nazwa `a;b.docx` 400, JSON jako `.pdf` 415, `POST /forms?report=true` z #3 docx 200 w 5.0 s za $0.0018, wynik przechodzi `/forms/validate`, SSE: `stage` ×6, `escalation`, `result`. Proces w kontenerze: `uid=10001(coi)`.

## 3.2 Zakres minimalny

| ID | Wymaganie | Stan | Dowód |
|---|---|---|---|
| M1 | REST API przyjmuje PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG | ✅ | `coi/parsing/detect.py` (`ALLOWED`), `GET /api/v1/info` → `extensions`; `tests/parsing/test_contract.py`, `test_detect.py`; wyniki docx, doc, jpg, png w `results/` |
| M2 | Zwraca JSON odpowiadający zawartości formularza | ✅ | `coi/pipeline.py` `convert()`; `results/*.coi.json` dla #1–#9 |
| M3 | JSON zgodny ze schematem i wzorcami #1, #5 | ✅ | `coi/generator/validate.py` (schemat z `form_schema.json` + R1–R6); wszystkie 11 wyników „Walidacja OK” w `results/README.md`; EVAL-3: #1 i #5 bez rozbieżności krytycznych ([ADR 0023](adr/0023-wzorce-ponad-schemat.md)) |
| M4 | Wymagania projektowania formularzy (strony tematyczne, Standardy, Reguły techniczne) | 🟡 | Strony „Dane”, przedmiot, „Kontakt i zgody”, koniec (`generator/templates/`), pola domyślnie REQUIRED ([ADR 0018](adr/0018-pola-domyslnie-wymagane.md)). EVAL-3: 22 rozbieżności krytyczne w #2–#9, głównie alternatywy, warunki, osoby trzecie ([results/eval-3/README.md](../results/eval-3/README.md)); część reguł G1–G17 wdrożona po EVAL-3 (commity `5c088ab`…`af98b50`), bez ponownego pomiaru |
| M5 | Dokumentacja architektury | ✅ | [architecture.md](architecture.md), [adr/](adr/README.md) |

## 3.3 Rozszerzenia

| ID | Wymaganie | Stan | Dowód |
|---|---|---|---|
| R-I | Słowniki i dane inicjalne przy pasujących polach | ✅ | `coi/dictionaries/` (katalog, `match()`), wyniki: `Kraje` ×43, `TERYT_4G_DOWODOWY` ×43; dane inicjalne `defaultValue: "MLPZ.*"` ([ADR 0022](adr/0022-dane-inicjalne-tylko-konfiguracja.md)); `tests/dictionaries/` |
| R-II | Propozycja nowego słownika | ✅ | `report.proposed_dictionaries` (#5, #7, #9 w `results/README.md`), `POST /api/v1/dictionaries/from-proposal`, CRUD słowników ([ADR 0021](adr/0021-nowy-slownik-tylko-z-lista-pozycji.md), [ADR 0025](adr/0025-propozycje-slownikow-tylko-w-raporcie.md)) |
| R-III | Zależności i dynamiczne przepływy (wybór użytkownika) | 🟡 | `states` SHOW z JSONata: 438 w wynikach, `$repeatingSectionIndex` w sekcjach powtarzalnych; walidator sprawdza odwołania JSONata. Przejścia między stronami liniowe (schemat nie ma warunków w `flow.links`) |
| R-IV | Frontend: wczytanie plików, przegląd JSON | ✅ | `frontend/src/App.tsx`: upload, postęp SSE, JSON, raport, historia, `PUT`, regeneracja |
| R-V | Wizualizacja JSON jako e-usługi | ✅ | `frontend/src/Preview.tsx`: strony, sekcje, pola, sekcje powtarzalne, słowniki, SHOW przez `jsonata` |
| R-VI | Walidacje (typ, długość, telefon, PESEL…) i UX (batch, makiety) | 🟡 | Walidatory z etykiet (`generator/adapter.py` `label_validators`): REQUIRED, ZIP_CODE, EMAIL, NIP, REGON, PESEL, EPUAP, ADE, SERIAL_NUMBER_ID_CARD; batch z kolejką (`VITE_BATCH_CONCURRENCY`). Brak walidatora telefonu (pole „Numer telefonu” w `templates/kontakt.json` bez walidatora; schemat zadania nie ma takiej nazwy) |

## 4. Oddanie

| Element | Stan | Dowód |
|---|---|---|
| Opis i tytuł projektu | 🟡 | [README.md](../README.md) (opis techniczny); opisu na platformę zgłoszeń nie ma w repozytorium |
| Prezentacja PDF ≤ 10 slajdów | ❌ | brak w repozytorium |
| Wynikowe JSON-y (#2, #3, #4, #7, #8, #9) | 🟡 | `results/*.coi.json` są, ale z obrazu HEAD `c935629` (16 commitów przed HEAD) |
| Film ≤ 3 min (link) | ❌ | brak |
| Repozytorium kodu | ✅ | `app/` (git) |
| Zrzuty, demo, grafiki (opcjonalne) | ❌ | brak |

## 5. Wymagania techniczne

| ID | Wymaganie | Stan | Dowód |
|---|---|---|---|
| T1 | Python 3.14+ | ✅ | `python:3.14.10-slim-trixie`, `pyproject.toml` ([ADR 0002](adr/0002-python-314-uv-licencje.md)) |
| T2 | Open source bez copyleftu, najnowsze stabilne | ✅ | Flask, APIFlask, Kreuzberg, PyJWT, SQLAlchemy, Tesseract (Apache-2.0), React, Vite ([ADR 0002](adr/0002-python-314-uv-licencje.md)); brak automatycznego skanu licencji w CI |
| T3 | Bez zewnętrznych API/SaaS i modeli tylko przez API | 🟡 | Eden to wyjątek mentorów ([flow-scenarios.md](flow-scenarios.md)); tryb `LLM_PROVIDER=local` z otwartymi wagami bez ruchu wychodzącego (`tests/parsing/test_airgap.py`, [ADR 0010](adr/0010-adapter-dostawcy-modeli-i-air-gap.md)). Domyślne modele (Mistral przez Eden) częściowo nie mają otwartych wag; air gap nie był uruchamiany na prawdziwym modelu lokalnym na pełnym zestawie |
| T4 | Jeden plik | ✅ | `coi/api.py` (`Upload`, więcej plików → 400), `tests/api/test_api.py` |
| T5 | Tylko obsługiwane formaty, MIME zgodny z rozszerzeniem | ✅ | `detect.py` (filetype, magic bytes), 415 sprawdzone na obrazie |
| T6 | Nazwa ≤ 250, bez `; : > < / \ | ' * % $` | ✅ | `coi/api.py` (`FORBIDDEN`, `MAX_FILENAME_LEN`, surowy `Content-Disposition` dla `\`), `test_400_bad_name`, `test_400_raw_backslash_in_filename`, 400 na obrazie |
| T7 | Rozmiar konfigurowalny | ✅ | `MAX_FILE_MB` → `MAX_CONTENT_LENGTH` (backend) i `client_max_body_size` (nginx frontu, `MAX_FILE_MB` + 1 MB, runtime), 413 `problem+json` w obu, `test_413` |
| T8 | Plik tylko w pamięci / tymczasowo | ✅ | Backend: `InMemoryRequest` (`coi/__init__.py`), upload w RAM. Przestrzeń tymczasowa na czas żądania, kasowana po nim: `TemporaryDirectory` w `parsing/pipeline.py` i `parsers/tesseract.py` (obrazy stron) oraz bufor ciała żądania w nginx frontu (`/tmp/client_temp`). W bazie wynik, `report`, `editor` (w tym `editor.source`, tekst z pliku), nazwa i sha256, bez bajtów pliku ([storage.md](storage.md)); sprawdzone smoke'iem ([smoke-compliance.md](smoke-compliance.md)) |
| T9 | Kompletny Docker | ✅ | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` |
| T10 | Oficjalne lekkie obrazy, wersje, bez `latest`, bez roota, porty, sekrety w runtime | 🟡 | Wersje przypięte, `coi` uid 10001 i `nginx` uid 101, po jednym porcie, `env_file`. Backend na `slim`, nie Alpine (Kreuzberg bez wheeli musl, uzasadnione w [backend/README.md](../backend/README.md#docker)); front na `nginxinc/nginx-unprivileged` (wydawca NGINX) oraz `ghcr.io/astral-sh/uv` (tylko build backendu, wydawca Astral) to nie „Docker Official Image”. Bundle frontu bez tokenu; token demo jest tymczasowo wstrzykiwany w runtime (`/config.js`, `DEMO_API_TOKEN`, [ADR 0015](adr/0015-jwt-tylko-weryfikacja.md), dopisek). Healthchecki są w `docker-compose.yml`, nie w `HEALTHCHECK` obrazów |
| T11 | Konfiguracja: rozmiar, JWT, integracje | ✅ | `coi/config/`, `.env.example` i tabela w README zgodne z kodem (lista zmiennych sprawdzona 2026-11-22) |
| T12 | README: build, uruchomienie, konfiguracja, REST API | ✅ | [README.md](../README.md) |

## 6. Testowanie na nowych plikach

🟡 Reguły ogólne ([ADR 0024](adr/0024-uniwersalne-reguly-bez-poprawek-pod-formularz.md)), bramki z eskalacją i raport `needs_review`. Ryzyko: czas (#8, #9: 3–4 min synchronicznie) i jakość na formularzach z wieloma wariantami. Brak zestawu „nowych” plików spoza materiałów do testu odporności.

## 8. Kryteria oceny: mocne strony

| Kryterium | Co je wspiera |
|---|---|
| Kompletność (30%) | minimum + R-I…R-VI (R-III i R-VI częściowo) |
| Intuicyjność (20%) | podgląd e-usługi, postęp SSE, raport `needs_review` z mapą źródła, batch |
| Jakość kodu (20%) | kontrakty (`ParsedDocument`, `FieldTree`), 261 testów, 27 ADR-ów |
| Potencjał wdrożeniowy (20%) | ~$0.02 na formularz, RS256/JWKS, PostgreSQL przez URL, air gap, Docker bez roota |
| Oryginalność (10%) | drabina eskalacji z bramką i świadkiem OCR, edytor z mapą źródła, regeneracja bez LLM |

## Luki

Zamknięte w tym przeglądzie (dokumentacja i konfiguracja): główny `README.md` (T12), [architecture.md](architecture.md) (M5), `EXTRACTION_*` w `.env.example` (T11), kontrakt parsera i scenariusze przeniesione do repo, nieaktualne dokumenty oznaczone.

Otwarte, w kolejności priorytetu:

| P | Luka | Rodzaj | Co zrobić |
|---|---|---|---|
| P0 | Prezentacja PDF, film ≤ 3 min, opis projektu (pkt 4) | oddanie | przygotować poza kodem |
| P0 | Wyniki w `results/` z HEAD `c935629`, nie z bieżącego kodu | proces | ponowny przebieg `results/run.py` na HEAD i aktualizacja `results/README.md` (koszt około $0.25) |
| P1 | M4: rozbieżności krytyczne z EVAL-3 (#8: 11, #9: 3, #7: 3) | kod | dokończyć reguły G1–G11 i zmierzyć ponownie (EVAL-4) |
| P1 | Czas #8 i #9 (3–4 min w jednym żądaniu) na obronie z nowymi plikami | kod | rozważyć tańszy pierwszy szczebel albo równoległość ekstrakcji; front już pokazuje postęp SSE |
| P2 | R-VI: brak walidatora telefonu | kod | sprawdzić w „Regułach technicznych”, czy jest nazwa walidatora telefonu; jeśli tak, dodać do `label_validators` i `kontakt.json` |
| P2 | R-III: brak warunkowych przejść między stronami | ograniczenie schematu | tylko opis w dokumentacji |
| P2 | T3: domyślne modele przez Eden; air gap nie sprawdzony end-to-end na prawdziwym modelu | kod/test | jeden przebieg z Ollamą `qwen3-vl:8b` i lokalnym modelem ekstrakcji |
| P3 | Healthchecki tylko w `docker-compose.yml`, obrazy bez `HEALTHCHECK`; front sprawdza `/`, nie łączność z backendem | konfiguracja | dodać `HEALTHCHECK` do Dockerfile'i, jeśli obrazy będą uruchamiane bez compose |
| P3 | Linki w ADR-ach do plików spoza repo (`poc-1-ocr/`, `HANDOFF.md`) | dokumentacja | poza repo nie zadziałają; flow-review i spec parsera podmienione na kopie w `docs/` |
| P3 | Niezacommitowane zmiany innych wątków (`DELETE /forms/{id}`, `/resolved`, front shadcn) | proces | commit właściciela; README już je wymienia |
