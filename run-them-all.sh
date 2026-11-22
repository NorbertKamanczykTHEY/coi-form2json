#!/usr/bin/env bash
# Starts the whole app (backend + frontend) in Docker, waits for health, prints links and a demo token.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Utworzono .env z .env.example – wpisz EDENAI_API_KEY i JWT_SECRET, potem uruchom ponownie." >&2
  exit 1
fi

docker compose -p app up --build -d

echo -n "Czekam na zdrowe kontenery"
for _ in $(seq 1 90); do
  status=$(docker compose -p app ps --format '{{.Health}}' | sort -u | tr '\n' ' ')
  [[ "$status" == "healthy " ]] && break
  echo -n "."; sleep 2
done
echo

token=$(docker compose -p app exec -T backend python -m coi.make_token demo --hours 24 | tail -1)

cat <<EOF

Gotowe:
  Frontend    http://localhost:8080
  Swagger UI  http://localhost:8000/docs
  OpenAPI     http://localhost:8000/openapi.json
  Healthcheck http://localhost:8000/healthz

Token JWT (24 h) – wklej w UI („Token”) albo w Swaggerze („Authorize”):
$token

Stop: docker compose -p app down   (dane zostają; -v usuwa bazę)
EOF
