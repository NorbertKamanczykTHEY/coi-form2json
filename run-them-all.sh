#!/usr/bin/env bash
# Starts the whole app (backend + frontend) in Docker, waits for health, prints links and a demo token.
# shortcut: a fresh 7-day demo JWT is written to .env (DEMO_API_TOKEN) and served to the frontend, so the UI needs no login; IdP login replaces it (ADR 0015, addendum).
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Utworzono .env z .env.example – wpisz EDENAI_API_KEY i JWT_SECRET, potem uruchom ponownie." >&2
  exit 1
fi

docker compose -p app build backend
token=$(docker compose -p app run --rm --no-deps -T backend python -m coi.make_token demo --hours 168 | tail -1)
[[ "$token" == eyJ* ]] || { echo "Nie udało się wygenerować tokenu (czy JWT_SECRET jest w .env?)." >&2; exit 1; }
{ grep -v '^DEMO_API_TOKEN=' .env || true; echo "DEMO_API_TOKEN=$token"; } > .env.new && mv .env.new .env

docker compose -p app up --build -d

echo -n "Czekam na zdrowe kontenery"
for _ in $(seq 1 90); do
  status=$(docker compose -p app ps --format '{{.Health}}' | sort -u | tr '\n' ' ')
  [[ "$status" == "healthy " ]] && break
  echo -n "."; sleep 2
done
echo
[[ "$status" == "healthy " ]] || { echo "Kontenery nie są zdrowe: docker compose -p app ps / logs" >&2; exit 1; }

cat <<EOF

Gotowe:
  Frontend    http://localhost:8080
  Swagger UI  http://localhost:8000/docs
  OpenAPI     http://localhost:8000/openapi.json
  Healthcheck http://localhost:8000/healthz

! TYLKO DO TESTÓW: token demo poniżej jest wbudowany w konfigurację frontu (bez logowania).
! Docelowo logowanie przez IdP (ADR 0015). Nie używaj go na produkcji.
Token JWT (7 dni, też w .env jako DEMO_API_TOKEN) do Swaggera („Authorize”) i curl:
$token

Stop: docker compose -p app down   (dane zostają; -v usuwa bazę)
EOF
