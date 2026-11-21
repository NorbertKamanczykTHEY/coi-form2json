# 0016. Błędy RFC 9457, OpenAPI z APIFlask, batch we froncie
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (T12, R-VI) + ZESPÓŁ

## Kontekst
- Wymóg T12: README opisuje REST API. Rozszerzenie R-VI: UX z batchem. Zadanie nie wskazuje formatu błędów ani sposobu opisu API.
- Wymóg T4 zostaje: API przyjmuje jeden plik ([0013](0013-post-forms-synchronicznie.md)).

## Decyzja
- Błędy w formacie RFC 9457 (`application/problem+json`) z dodatkowym polem `code`, jeden format dla frontu i dla jury.
- OpenAPI 3.1 generuje APIFlask z kodu, Swagger UI pod `/docs`. Front generuje typy narzędziem `openapi-typescript`.
- Batch robi frontend: N równoległych wywołań `POST /forms`. Endpointu batch nie ma.
- Prefiks `/api/v1`.

## Konsekwencje
- Opis API ma jedno źródło (kod), a README linkuje do `/docs` zamiast go kopiować.
- Klient spoza naszego frontu musi sam zrobić batch.
- Równoległe wywołania zwielokrotniają obciążenie i koszt modeli. Dokumenty nie określają limitu równoległości we froncie.
