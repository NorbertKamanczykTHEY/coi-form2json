# ADR-y

Decyzje projektu w formacie krótkiego Nygarda (kontekst, decyzja, konsekwencje). Kolumna „Źródło” pokazuje, skąd wynika decyzja:

- **SPEC (ID)**: wymóg treści zadania, ID z [requirements.md](../requirements.md) (np. T5, M3, R-II),
- **MENTORZY**: odpowiedź mentorów z 2026-11-21 ([flow-review](../../../research/2026-11-21-flow-review.md)),
- **ZESPÓŁ**: nasz wybór, bez wymogu w zadaniu.

Gdy decyzja wynika ze specyfikacji tylko częściowo, są dwa źródła, a Kontekst oddziela wymóg od naszego wyboru.

| Nr | Tytuł | Status | Źródło | Plik |
|---|---|---|---|---|
| 0001 | Monorepo `app/`: Flask (APIFlask) i Vite + React + shadcn | przyjęta | SPEC (T1, R-IV) + ZESPÓŁ | [0001-monorepo-flask-vite-react.md](0001-monorepo-flask-vite-react.md) |
| 0002 | Python 3.14, uv i licencje bez copyleftu | przyjęta | SPEC (T1, T2) + ZESPÓŁ | [0002-python-314-uv-licencje.md](0002-python-314-uv-licencje.md) |
| 0003 | Każdy moduł we własnym Dockerfile i kontenerze | przyjęta | SPEC (T9, T10) + ZESPÓŁ | [0003-kontener-na-modul.md](0003-kontener-na-modul.md) |
| 0004 | Jedno publiczne API, usługi pomocnicze w sieci wewnętrznej | przyjęta | SPEC (T4, T10) + ZESPÓŁ | [0004-jedno-publiczne-api.md](0004-jedno-publiczne-api.md) |
| 0005 | Mapa typ pliku → parsery i kontrakt `ParsedDocument` | przyjęta | ZESPÓŁ | [0005-mapa-parserow-i-parseddocument.md](0005-mapa-parserow-i-parseddocument.md) |
| 0006 | Wykrywanie typu pliku: rozszerzenie i MIME z magic bytes | przyjęta | SPEC (T5) + ZESPÓŁ | [0006-wykrywanie-typu-pliku.md](0006-wykrywanie-typu-pliku.md) |
| 0007 | T0 lokalnie (Kreuzberg + Tesseract), skany i obrazy do VLM | przyjęta | ZESPÓŁ | [0007-t0-lokalnie-skany-do-vlm.md](0007-t0-lokalnie-skany-do-vlm.md) |
| 0008 | Drabina eskalacji z bramką jakości | przyjęta | ZESPÓŁ | [0008-drabina-eskalacji-z-bramka.md](0008-drabina-eskalacji-z-bramka.md) |
| 0009 | Serwis parsowania kończy się na `ParsedDocument` | przyjęta | ZESPÓŁ | [0009-parsowanie-konczy-sie-na-parseddocument.md](0009-parsowanie-konczy-sie-na-parseddocument.md) |
| 0010 | Modele za adapterem dostawcy, tryb air gap | przyjęta | SPEC (T3) + MENTORZY + ZESPÓŁ | [0010-adapter-dostawcy-modeli-i-air-gap.md](0010-adapter-dostawcy-modeli-i-air-gap.md) |
| 0011 | Sekrety tylko w `.env` i zmiennych środowiskowych | przyjęta | SPEC (T10, T11) + ZESPÓŁ | [0011-sekrety-tylko-w-env.md](0011-sekrety-tylko-w-env.md) |
| 0012 | Decyzja „istniejący / nowy / bez słownika”: model klasyfikacyjny | proponowana | SPEC (R-I, R-II) + ZESPÓŁ | [0012-decyzja-o-slowniku-modelem-klasyfikacyjnym.md](0012-decyzja-o-slowniku-modelem-klasyfikacyjnym.md) |
| 0013 | `POST /api/v1/forms`: jeden plik, odpowiedź synchroniczna | przyjęta | SPEC (T4, M2, M3) + ZESPÓŁ | [0013-post-forms-synchronicznie.md](0013-post-forms-synchronicznie.md) |
| 0014 | Postęp przez SSE w tym samym żądaniu, bez kolejki zadań | przyjęta | ZESPÓŁ | [0014-postep-przez-sse.md](0014-postep-przez-sse.md) |
| 0015 | JWT: API tylko weryfikuje, bez endpointu logowania | przyjęta | SPEC (T11) + ZESPÓŁ | [0015-jwt-tylko-weryfikacja.md](0015-jwt-tylko-weryfikacja.md) |
| 0016 | Błędy RFC 9457, OpenAPI z APIFlask, batch we froncie | przyjęta | SPEC (T12, R-VI) + ZESPÓŁ | [0016-bledy-rfc-9457-openapi-batch-we-froncie.md](0016-bledy-rfc-9457-openapi-batch-we-froncie.md) |
| 0017 | Baza: SQLite na wolumenie za SQLAlchemy, przełączana przez `DATABASE_URL` | przyjęta | SPEC (T8, R-II) + ZESPÓŁ | [0017-sqlite-za-sqlalchemy.md](0017-sqlite-za-sqlalchemy.md) |
| 0018 | Pola domyślnie wymagane | przyjęta | SPEC (M4) + MENTORZY | [0018-pola-domyslnie-wymagane.md](0018-pola-domyslnie-wymagane.md) |
| 0019 | Bez pól wyliczanych | przyjęta | MENTORZY + ZESPÓŁ | [0019-bez-pol-wyliczanych.md](0019-bez-pol-wyliczanych.md) |
| 0020 | Formularz #9: jeden formularz, radio „rodzaj wniosku” i flow liniowy | przyjęta | MENTORZY + SPEC (R-III) | [0020-formularz-9-jeden-formularz.md](0020-formularz-9-jeden-formularz.md) |
| 0021 | Nowy słownik tylko wtedy, gdy mamy listę pozycji | przyjęta | SPEC (R-II) + ZESPÓŁ | [0021-nowy-slownik-tylko-z-lista-pozycji.md](0021-nowy-slownik-tylko-z-lista-pozycji.md) |
| 0022 | Dane inicjalne: konfigurujemy źródło i atrybut, niczego nie wypełniamy | proponowana | SPEC (R-I) + ZESPÓŁ | [0022-dane-inicjalne-tylko-konfiguracja.md](0022-dane-inicjalne-tylko-konfiguracja.md) |
| 0023 | Przy rozbieżności schematu i wzorców trzymamy się wzorców #1 i #5 | proponowana | SPEC (M3) + ZESPÓŁ | [0023-wzorce-ponad-schemat.md](0023-wzorce-ponad-schemat.md) |
| 0024 | Reguły, prompty i bramki są uniwersalne, bez poprawek pod konkretny formularz | przyjęta | ZESPÓŁ | [0024-uniwersalne-reguly-bez-poprawek-pod-formularz.md](0024-uniwersalne-reguly-bez-poprawek-pod-formularz.md) |
| 0025 | Propozycje słowników tylko w raporcie i w edytorze, JSON COI ma wyłącznie słowniki istniejące | przyjęta | UŻYTKOWNIK | [0025-propozycje-slownikow-tylko-w-raporcie.md](0025-propozycje-slownikow-tylko-w-raporcie.md) |
| 0026 | Wnioskodawca „tylko podmiot”: bez pola „w czyim imieniu”, odpis z rejestru według dokumentu, dowód pełnomocnika | przyjęta | UŻYTKOWNIK | [0026-wnioskodawca-tylko-podmiot.md](0026-wnioskodawca-tylko-podmiot.md) |
| 0027 | „Tylko osobiście” z dokumentu, przełącznik w edytorze bez ponownego LLM | przyjęta | UŻYTKOWNIK | [0027-tylko-osobiscie-i-regeneracja.md](0027-tylko-osobiscie-i-regeneracja.md) |
