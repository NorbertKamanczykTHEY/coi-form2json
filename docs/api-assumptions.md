# API i konfiguracja: założenia (szkic do decyzji)

Status: zaakceptowane (Q11–Q15) · 2026-11-21

## Wymagania z treści zadania (pkt 3.2, 3.3, 5)
- REST API przyjmuje **jeden plik** (pdf, doc, docx, ods, xlsx, jpg, jpeg, png) i zwraca **JSON gotowy do importu** w Generatorze Formularzy COI.
- Typ MIME musi się zgadzać z rozszerzeniem. Nazwa pliku ma ≤ 250 znaków i nie zawiera `; : > < / \ | ' * % $`. Maksymalny rozmiar pliku ustawia parametr aplikacji.
- Plik istnieje tylko w pamięci albo w katalogu tymczasowym, i tylko na czas żądania.
- JWT z parametrami w konfiguracji. Konfiguracja obejmuje: maksymalny rozmiar pliku, JWT i parametry integracji (LLM).
- Docker: oficjalne obrazy, lekkie, jawne wersje, bez `latest`, użytkownik bez roota, tylko potrzebne porty, sekrety podawane w runtime.
- README: budowanie obrazu, uruchomienie, konfiguracja, opis REST API.
- Rozszerzenia: II nowy słownik, IV frontend (wczytanie pliku i przegląd JSON), V wizualizacja e-usługi z JSON, VI walidacje i UX (batch, makiety).
- Na obronie aplikację uruchamia się na **nowych plikach**.

## Założenia
| # | Założenie | Dlaczego |
|---|---|---|
| A1 | Prefiks `/api/v1`, JSON, błędy w formacie RFC 9457 `application/problem+json` z polem `code` | Jeden format błędów dla frontu i dla jury |
| A2 | **Główne wywołanie jest synchroniczne**: `POST /api/v1/forms` (multipart, pole `file`) zwraca JSON formularza | Spełnia minimum dosłownie. Plik żyje tylko w czasie żądania |
| A3 | Postęp: to samo żądanie z `Accept: text/event-stream` zwraca strumień zdarzeń (`stage`, `escalation`, `warning`), a na końcu `result` | Front pokazuje kroki (T0 → VLM, bramka) bez kolejki zadań i bez trzymania pliku po zakończeniu żądania |
| A4 | Domyślna odpowiedź to **czysty JSON COI**, który można zaimportować bez obróbki. `?report=true` zwraca kopertę `{id, form, report}`, gdzie raport zawiera `trace`, `warnings`, `needs_review`, koszt i czas. `?editor=true` dokłada `editor`: `source` (ParsedDocument: strony i bloki) oraz `field_map` (fieldId → strona, blok, bbox, confidence, needs_review), czyli dane do edytora na FE | Wynik dla COI zostaje czysty, urzędnik i demo mają audyt, a edytor pokazuje, skąd wzięło się każde pole |
| A5 | **Backend tylko weryfikuje JWT** (`Authorization: Bearer`): HS256 ze wspólnym sekretem albo RS256 z JWKS z zewnętrznego IdP. Wszystkie ustawienia i sekrety są w `.env`. Endpointu logowania nie ma. Do demo jest skrypt `make-token`, który generuje token z `JWT_SECRET`. Front nie ma logowania: użytkownik wkleja token | Wymóg JWT, gotowe pod IdP urzędu (potencjał wdrożeniowy) |
| A6 | Kody: 400 brak pliku, więcej niż jeden plik albo zła nazwa · 401 · 413 za duży · 415 typ lub MIME · 422 nie udało się odczytać formularza · 502/504 błąd lub timeout LLM | Zgodnie ze specem parsera (413/415) |
| A7 | Słowniki: `GET /api/v1/dictionaries` zwraca katalog (z materiałów i nasze). `POST /api/v1/dictionaries` tworzy nowy słownik `{id, name, items[]}`. Generator może też zaproponować nowy słownik, który trafia do `report.proposed_dictionaries`. Zapis w **SQLite na wolumenie** | Rozszerzenie II. Decyzja użytkownika z wcześniejszego wątku (p4) |
| A7b | Formularze: każdy wynik `POST /forms` zapisujemy w SQLite (JSON COI, raport, nazwa pliku, sha256, `created_by` = `sub` z JWT, czas). **Przesłanego pliku nie zapisujemy.** `GET /api/v1/forms` zwraca listę, `GET /api/v1/forms/{id}` jeden formularz (te same `?report` / `?editor`), `PUT /api/v1/forms/{id}` zapisuje JSON poprawiony w edytorze (po walidacji A8). MVP: każdy uwierzytelniony użytkownik widzi wszystko | Historia i edytor na FE. Plik żyje tylko w czasie żądania, w bazie zostaje tylko wynik |
| A8 | `POST /api/v1/forms/validate` przyjmuje JSON COI i zwraca listę naruszeń (schemat i reguły 1–6) | Front sprawdza ręczne poprawki, jury może zweryfikować wynik |
| A9 | `GET /healthz` (żywotność) i `GET /api/v1/info` (wersja, aktywne szczeble modeli, limity) bez JWT | Docker healthcheck. Front pokazuje limity przed wysłaniem pliku |
| A10 | Batch robi frontend: N równoległych wywołań A2/A3, bez endpointu batch | API zostaje „jeden plik”, a UX batch i tak mamy |
| A11 | OpenAPI 3.1 generowane z kodu przez **APIFlask** (MIT, nadbudowa Flaska) ze Swagger UI pod `/docs`. Front generuje typy przez `openapi-typescript` | „Opis REST API” z jednego źródła, typy dla frontu za darmo |
| A12 | CORS wyłączony. Front w produkcji idzie przez nginx z tym samym originem (`/api` → backend). W dev działa proxy Vite | Mniej konfiguracji i mniejsza powierzchnia ataku |

## Konfiguracja (zmienne środowiskowe, wszystkie w `.env.example`)
| Zmienna | Domyślnie | Uwagi |
|---|---|---|
| `MAX_FILE_MB` | 20 | wymóg zadania |
| `MAX_FILENAME_LEN` | 250 | stała z zadania, w env dla przejrzystości |
| `JWT_ALG` | HS256 | HS256 albo RS256 |
| `JWT_SECRET` | brak | dla HS256, sekret w runtime |
| `JWT_JWKS_URL` | brak | dla RS256 (IdP urzędu) |
| `JWT_ISSUER` / `JWT_AUDIENCE` / `JWT_LEEWAY_S` | brak / brak / 30 | sprawdzane, jeśli są ustawione |
| `DATABASE_URL` | `sqlite:////data/coi.sqlite` | SQLAlchemy (ADR 0017); na produkcji inna baza. `DB_PATH` działa jako alias |
| `LLM_BASE_URL` | `https://api.edenai.run/v3` | dowolny endpoint zgodny z OpenAI (vLLM, Ollama). Wymóg regulaminu |
| `LLM_API_KEY` (alias `EDENAI_API_KEY`) | brak | sekret |
| `LADDER_PATH` | wbudowany `ladder.json` | szczeble modeli, podmiana bez kodu |
| `LLM_TIMEOUT_S` / `REQUEST_TIMEOUT_S` | 60 / 300 | #9 ma 16 stron |
| `MAX_PAGES` | 30 | ochrona kosztu |
| `LOG_LEVEL` | INFO | bez treści plików i bez kluczy w logach |
| `PORT` | 8000 | jeden port na kontener |
| Front: `API_UPSTREAM` | `http://backend:8000` | szablon nginx w runtime |

## Frontend (Vite + React + TS + shadcn/ui, kontener nginx-unprivileged)
1. **Token**: pole „wklej token JWT” (trzymany w sessionStorage), bez logowania.
2. **Import**: przeciąganie wielu plików, walidacja nazwy, rozszerzenia i rozmiaru po stronie klienta (limity z `/info`), kolejka z postępem z A3.
3. **Wynik**, zakładki:
   - **Podgląd e-usługi**: render stron, sekcji i pól z JSON, z działającymi `states` SHOW przez bibliotekę `jsonata` (rozszerzenie V).
   - **JSON**: przeglądarka drzewa, kopiowanie, pobieranie `.json`.
   - **Raport**: ścieżka ekstrakcji, ostrzeżenia, pola `needs_review`, koszt.
   - **Walidacja**: wynik A8.
4. **Historia**: lista zapisanych formularzy (A7b), otwarcie w widoku wyniku, edycja i zapis.
5. **Słowniki**: katalog i formularz nowego słownika (A7).

## Moduły i kontenery
`backend` (Flask + gunicorn, port 8000) · `frontend` (nginx, port 8080) · opcjonalnie `kreuzberg`, jeśli wątek parsowania go wydzieli (sieć wewnętrzna, bez portu). Każdy moduł ma własny Dockerfile i da się go uruchomić osobno.

## Poza zakresem
Kolejka zadań, przechowywanie przesłanych plików, konta i uprawnienia per użytkownik, logowanie w UI, edycja formularza w UI (najwyżej poprawki JSON z walidacją A8).
