# COI backend

## REST API

Interaktywny opis (Swagger UI): **http://localhost:8000/docs**. Specyfikacja OpenAPI 3.1: `/openapi.json`. Założenia: `app/docs/api-assumptions.md`, baza danych: `app/docs/storage.md`.

Wszystko pod `/api/v1` wymaga nagłówka `Authorization: Bearer <JWT>`. Wyjątki to `/api/v1/info`, `/healthz` i `/docs`. Backend tylko weryfikuje token: HS256 z `JWT_SECRET` albo RS256 z kluczy `JWT_JWKS_URL`. Opcjonalnie sprawdza `JWT_ISSUER`, `JWT_AUDIENCE` i `JWT_LEEWAY_S`. Token musi zawierać `sub` i `exp`.

| Metoda i ścieżka | Co robi | Kody |
|---|---|---|
| `POST /api/v1/forms` | multipart, pole `file`: jeden plik → JSON COI. `?report=true` zwraca `{id, form, report}`, `?editor=true` dokłada `editor`. `Accept: text/event-stream` włącza SSE | 200, 400, 401, 413, 415, 422, 502, 504 |
| `GET /api/v1/forms` | lista zapisanych formularzy (same metadane) | 200, 401 |
| `GET /api/v1/forms/{id}` | jeden formularz, te same `?report` i `?editor` | 200, 401, 404 |
| `PUT /api/v1/forms/{id}` | zapis poprawionego JSON-a po walidacji | 200, 400, 401, 404, 422 |
| `POST /api/v1/forms/validate` | `{valid, errors[{path, message, rule}]}` | 200, 400, 401 |
| `GET /api/v1/info` | wersja, limity, szczeble modeli (bez tokena) | 200 |
| `GET /healthz` | żywotność (bez tokena) | 200 |

Błędy mają format RFC 9457 `application/problem+json`: `{type, title, status, detail, code}`, a dla walidacji dodatkowo `errors`. Kody 413 i 415 pochodzą z `parse()` (rozszerzenie i magic bytes muszą do siebie pasować). Kod 400 oznacza brak pliku, więcej niż jeden plik albo złą nazwę (> 250 znaków albo któryś ze znaków `; : > < / \ | ' * % $`).

Przesłany plik jest tylko w pamięci, na czas żądania. W bazie zostaje wynik, nazwa pliku i jego sha256. W logach nie ma treści pliku, jego nazwy ani tokenów.

### Przykłady

```bash
# token demo (HS256, podpisany JWT_SECRET z app/.env)
TOKEN=$(docker compose exec -T backend python -m coi.make_token jan.kowalski)
# lokalnie: cd backend && uv run python -m coi.make_token

# konwersja: czysty JSON COI (id jest w nagłówku Location)
curl -i -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.docx" http://localhost:8000/api/v1/forms

# z raportem i danymi dla edytora
curl -H "Authorization: Bearer $TOKEN" -F "file=@wniosek.pdf" "http://localhost:8000/api/v1/forms?report=true&editor=true"

# postęp przez SSE
curl -N -H "Authorization: Bearer $TOKEN" -H "Accept: text/event-stream" -F "file=@wniosek.png" http://localhost:8000/api/v1/forms

# historia, odczyt, poprawka, walidacja
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/forms
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/forms/<id>
curl -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @form.json http://localhost:8000/api/v1/forms/<id>
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @form.json http://localhost:8000/api/v1/forms/validate
```

Strumień SSE. `stage`, `escalation` i `warning` mogą pojawić się wiele razy. Na końcu przychodzi `result`: jego `data` to ta sama treść co w zwykłym wywołaniu, a pole SSE `id:` to id formularza. Zamiast `result` może przyjść `error` z treścią problem+json. Błędy po starcie strumienia (np. 415 z `parse()`) przychodzą jako `event: error`, bo status 200 został już wysłany.

```
event: stage
data: {"stage": "parse", "status": "start"}

event: stage
data: {"stage": "parse", "status": "done", "seconds": 0.01, "parser": "kreuzberg"}

event: stage
data: {"stage": "generate", "status": "start"}

event: stage
data: {"stage": "generate", "status": "done"}

id: 12a41a1f-51e5-470e-917b-0d0095c90cd1
event: result
data: {"title": "wniosek1", "tabs": [...], "flow": {...}}
```

### Konfiguracja API
Zmienne opisuje `app/.env.example`: `JWT_SECRET`, `JWT_ALG`, `JWT_JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_LEEWAY_S`, `MAX_FILE_MB`, `MAX_FILENAME_LEN`, `DB_PATH` i `LOG_LEVEL`. Poza Dockerem ustaw `DB_PATH=./data/coi.sqlite`, bo domyślne `/data` istnieje tylko w kontenerze.

### Testy
`uv run pytest tests/api`: 401, 400, 413, 415, konwersja #1 docx, SSE, `?report` i `?editor`, zapis, odczyt i PUT z walidacją.
