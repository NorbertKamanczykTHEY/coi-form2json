# 0001. Monorepo `app/`: Flask (APIFlask) i Vite + React + shadcn
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (T1, R-IV) + ZESPÓŁ

## Kontekst
- Wymóg: backend w Javie 21+ albo Pythonie 3.14+ (T1). Zadanie chce też prostego frontendu do wczytania plików i przeglądu JSON (R-IV).
- Nasz wybór: Python, Flask z nadbudową APIFlask, frontend w Vite + React + shadcn/ui. shadcn wybraliśmy, bo jest dobrze udokumentowany. Żaden dokument nie wymusza tych bibliotek.
- Materiały konkursowe, PoC i research leżą obok `app/` i nie są częścią oddawanego kodu.

## Decyzja
- Jeden monorepo `app/` z katalogami `backend/` i `frontend/` oraz wspólnym `docker-compose.yml`.
- Repozytorium git istnieje tylko w `app/`. Materiały, PoC i research zostają poza nim.
- Backend: Flask + APIFlask. Frontend: Vite + React + TypeScript + shadcn/ui.

## Konsekwencje
- Typy frontu powstają z OpenAPI backendu (zob. [0016](0016-bledy-rfc-9457-openapi-batch-we-froncie.md)).
- Do repozytorium nie trafia nic z poza `app/`: PoC (`poc-1-ocr/`) i dokumenty badawcze trzeba linkować jako ścieżki lokalne.
- Wybór shadcn jest odwracalny: front komunikuje się z backendem wyłącznie przez REST.
