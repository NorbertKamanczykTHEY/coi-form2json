# COI frontend

Panel urzędnika cyfryzującego formularze:

- **Projekty**: lista formularzy z bazy (`GET /api/v1/forms`) z liczbą nierozstrzygniętych uwag, propozycjami słowników i oznaczeniem „nowe” dla importów z tej karty. Usuwanie z potwierdzeniem (`DELETE /api/v1/forms/{id}`).
- **Import plików**: kolejka w tle (działa po zamknięciu okna), `IMPORT_CONCURRENCY` plików naraz (`src/config.ts`, domyślnie 2, nadpisuje `VITE_BATCH_CONCURRENCY`). Przed wysłaniem sprawdza rozszerzenie, nazwę i rozmiar z `GET /api/v1/info`. Każdy wiersz rozwija czytelny log zdarzeń SSE (etapy, eskalacje, ostrzeżenia, koszt, czas). Zamknięcie karty w trakcie importu pyta o potwierdzenie.
- **Edytor projektu**: strony z czerwoną kropką, gdy mają nierozstrzygnięte uwagi (`report.needs_review`), pola wymagające decyzji z czerwoną ramką i powodem. Uwagę rozstrzyga poprawka pola albo „Akceptuję bez zmian”; stan trafia na serwer (`PUT /api/v1/forms/{id}/resolved`), poprawki formularza przez `PUT /api/v1/forms/{id}` z walidacją. Przyjmowanie proponowanych słowników i przełącznik „tylko osobiście” (przebudowa).
- **Makieta dla obywatela**: render bieżącego JSON-a (kroki, siatka x/y, typy pól, SHOW przez JSONata, sekcje powtarzalne, zgody). **Podgląd JSON** otwiera makietę dowolnego wklejonego lub wczytanego JSON-a COI bez zapisu.

Stos: Vite + React + TypeScript + Tailwind 4 + shadcn/ui (Radix), ikony lucide, krój Onest (lokalnie, `@fontsource-variable`). Typy API generuje `openapi-typescript` (`src/api.d.ts`).

## Token

Front nie ma logowania (ADR 0015). W bundlu nie ma żadnego tokenu ani sekretu, a `.env` nie trafia do obrazu (`.dockerignore`). Dwa tryby:

- **Tymczasowo, do testów (`shortcut:`):** gdy kontener ma `DEMO_API_TOKEN` (ustawia je `run-them-all.sh`), nginx serwuje go jako `/config.js`, front go używa i nie pokazuje pola „Token”. Każdy, kto otworzy stronę, może go odczytać. Docelowo logowanie przez IdP (ADR 0015, dopisek).
- **Bez tokenu w konfiguracji:** urzędnik wkleja token JWT; trzymamy go w `sessionStorage` tej karty.

```bash
cd ../backend && uv run python -m coi.make_token demo --hours 720   # token do wklejenia w UI
```

## Dev

```bash
npm install
API_UPSTREAM=http://localhost:8000 npm run dev   # proxy Vite: /api i /healthz -> backend, bez CORS
npm run build && npm run lint
# E2E (Playwright) na działających serwerach; importuje 3 pliki z materials/ (prawdziwe wywołania LLM, ok. 2-5 min)
E2E_URL=http://localhost:5173 E2E_TOKEN="$(cd ../backend && uv run python -m coi.make_token e2e)" npx playwright test
API_UPSTREAM=http://localhost:8000 npm run gen:api   # odśwież src/api.d.ts z /openapi.json
```

## Docker

Obraz: `node:24.11.1-alpine3.22` (build) → `nginxinc/nginx-unprivileged:1.29.3-alpine3.22`, port 8080, bez roota. Szablon `nginx/default.conf.template` jest renderowany przy starcie z `API_UPSTREAM` (domyślnie `http://backend:8000`), `/api` idzie do backendu z wyłączonym buforowaniem (SSE). Limit ciała żądania (`client_max_body_size`) wynika z `MAX_FILE_MB` (+1 MB) w runtime, a 413 z nginx ma postać `problem+json`. Obraz nie zawiera tokenu; healthcheck sprawdza `/`.

```bash
cd app && docker compose up --build   # front: http://localhost:8080
```
