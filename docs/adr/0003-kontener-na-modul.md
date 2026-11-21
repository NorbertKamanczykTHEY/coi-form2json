# 0003. Każdy moduł we własnym Dockerfile i kontenerze
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (T9, T10) + ZESPÓŁ

## Kontekst
- Wymóg T9: kompletna konfiguracja Docker, środowisko odizolowane. Wymóg T10: obrazy oficjalne i lekkie (w tabeli wymagań: Alpine), jawne wersje bez `latest`, użytkownik bez roota, tylko potrzebne porty, sekrety w runtime.
- Nasz wybór: osobny obraz na moduł, żeby dało się uruchamiać i wymieniać je niezależnie.
- Specyfikacja parsera dopuszcza `python:3.1x-slim` zamiast Alpine, gdy Kreuzberg na Alpine nie działa. W dokumentach nie ma potwierdzenia, że działa.

## Decyzja
- `backend` (Flask + gunicorn, port 8000) i `frontend` (nginx-unprivileged, port 8080) mają osobne Dockerfile i osobne kontenery. Opcjonalnie `kreuzberg`, jeśli wątek parsowania go wydzieli.
- Obrazy oficjalne i lekkie, z jawnymi wersjami (`python:3.14.10-slim-trixie`, `uv:0.11.9`), użytkownik bez roota, sekrety wyłącznie w runtime.
- Skład uruchamia `docker-compose.yml`. Każdy moduł da się też zbudować i uruchomić osobno.

## Konsekwencje
- Obraz backendu to `slim` (Debian), nie Alpine. To odstępstwo od brzmienia T10 i trzeba je uzasadnić w README albo zmienić obraz.
- Sekretów nie ma w warstwach obrazu (zob. [0011](0011-sekrety-tylko-w-env.md)).
- Więcej obrazów do utrzymania i aktualizowania wersji.
