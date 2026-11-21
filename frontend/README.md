# COI frontend

Prosty front do sprawdzania uploadu: wybór jednego lub kilku plików (każdy to osobne `POST /api/v1/forms?report=true` ze strumieniem SSE), postęp (`stage`, `escalation`, `warning`, `result`, `error`), limity z `GET /api/v1/info` sprawdzane przed wysłaniem, a na końcu JSON COI i raport jako sformatowany tekst.

Stos: Vite + React + TypeScript + Tailwind. Typy API generuje `openapi-typescript` (`src/api.d.ts`).

## Token (tylko demo)

Front nie ma logowania. Token JWT jest w `frontend/.env` jako `VITE_API_TOKEN` i trafia do nagłówka `Authorization: Bearer`.

```bash
cp .env.example .env
# wygeneruj token podpisany JWT_SECRET z app/.env i wpisz go do .env (bez wypisywania na ekran)
printf 'VITE_API_TOKEN=%s\n' "$(cd ../backend && uv run python -m coi.make_token demo-frontend --hours 720)" > .env
```

**Uwaga: Vite wkleja token do bundla JS, więc każdy, kto otworzy stronę, może go odczytać. To rozwiązanie wyłącznie na demo.** Na produkcji token musi przychodzić z logowania (IdP urzędu).

## Batch

Można wybrać kilka plików naraz: jeden plik to jeden formularz i jedno żądanie. Równolegle idzie najwyżej `VITE_BATCH_CONCURRENCY` żądań (w `frontend/.env`, domyślnie 3), reszta czeka w kolejce („w kolejce”). Wartość jest wbudowywana przy buildzie.

## Dev

```bash
npm install
API_UPSTREAM=http://localhost:8000 npm run dev   # proxy Vite: /api i /healthz -> backend, bez CORS
npm run build && npm run lint
API_UPSTREAM=http://localhost:8000 npm run gen:api   # odśwież src/api.d.ts z /openapi.json
```

## Docker

Obraz: `node:24.11.1-alpine3.22` (build) → `nginxinc/nginx-unprivileged:1.29.3-alpine3.22`, port 8080, bez roota. Szablon `nginx/default.conf.template` jest renderowany przy starcie z `API_UPSTREAM` (domyślnie `http://backend:8000`), `/api` idzie do backendu z wyłączonym buforowaniem (SSE). Token z `frontend/.env` jest wbudowywany przy `docker compose build frontend`.

```bash
cd app && docker compose up --build   # front: http://localhost:8080
```
