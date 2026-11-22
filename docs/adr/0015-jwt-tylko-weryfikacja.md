# 0015. JWT: API tylko weryfikuje, bez endpointu logowania
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (T11) + ZESPÓŁ

## Kontekst
- Zadanie wymaga JWT z parametrami w konfiguracji (T11). Nie określa, kto wystawia tokeny.
- Docelowo urząd ma własnego dostawcę tożsamości (IdP), co podnosi „potencjał wdrożeniowy”.

## Decyzja
- Backend weryfikuje nagłówek `Authorization: Bearer`. Algorytm: HS256 ze wspólnym sekretem (`JWT_SECRET`) albo RS256 z kluczami z JWKS (`JWT_JWKS_URL`). `JWT_ISSUER`, `JWT_AUDIENCE` i `JWT_LEEWAY_S` (domyślnie 30) są sprawdzane, jeśli ustawione.
- Cała konfiguracja jest w `.env` ([0011](0011-sekrety-tylko-w-env.md)). Endpointu logowania nie ma.
- Demo: skrypt `make-token` generuje token z `JWT_SECRET`. Front nie ma logowania, użytkownik wkleja token (trzymany w `sessionStorage`).
- Bez JWT działają tylko `GET /healthz` i `GET /api/v1/info`.

## Konsekwencje
- `created_by` w bazie to `sub` z tokenu. Konta i uprawnienia per użytkownik są poza zakresem MVP ([0017](0017-sqlite-za-sqlalchemy.md)).
- JWKS wymaga połączenia z IdP. W trybie air gap działa HS256 albo JWKS serwowany z sieci wewnętrznej.
- Brak unieważniania tokenów po stronie API: ważność kontroluje wystawca przez `exp`.

## Dopisek 2026-11-22: token demo we froncie i konwersja bez tokena (tymczasowo, do testów)
- **Token frontu (`shortcut:`).** `run-them-all.sh` przy każdym starcie generuje JWT (7 dni), zapisuje go w `.env` (`DEMO_API_TOKEN`, informacyjnie) i w env kontenera frontu. nginx serwuje go jako `/config.js` (runtime, bez przebudowy obrazu), a front nie pokazuje pola „Token”. Token nie jest w obrazie ani w bundlu JS, ale każdy, kto otworzy stronę, może go odczytać. Bez tokenu w konfiguracji front działa jak dotąd (wklejanie, `sessionStorage`).
- **Konwersja bez tokena.** `POST /api/v1/forms` i `POST /api/v1/forms/validate` przyjmują żądanie bez `Authorization` (`created_by = "anonymous"`). Nagłówek, jeśli jest, musi zawierać poprawny token, inaczej 401. Sterowanie: `AUTH_PUBLIC_CONVERT` (domyślnie `true`). W OpenAPI security tych dwóch operacji jest opcjonalne. Pozostałe endpointy zawsze wymagają JWT.
- **Docelowo:** logowanie przez IdP urzędu (RS256, JWKS), `AUTH_PUBLIC_CONVERT=false`, usunięcie `/config.js`. Backend nigdy nie zależy od tokenu frontu: przyjmuje każdy poprawny JWT (Swagger, curl, inni klienci).
