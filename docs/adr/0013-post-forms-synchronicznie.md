# 0013. `POST /api/v1/forms`: jeden plik, odpowiedź synchroniczna
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (T4, M2, M3) + ZESPÓŁ

## Kontekst
- Wymogi: API przyjmuje jeden plik (T4) i zwraca JSON zgodny ze strukturą oczekiwaną, gotowy do importu w Generatorze COI (M2, M3). Plik istnieje tylko na czas żądania (T8).
- Nasz wybór: synchroniczne wywołanie i czysty JSON jako domyślna odpowiedź ([api-assumptions](../api-assumptions.md), A2, A4, A6).

## Decyzja
- `POST /api/v1/forms`, multipart, pole `file`, dokładnie jeden plik. Odpowiedź w tym samym żądaniu.
- Domyślnie ciało to czysty JSON COI do importu bez obróbki. `?report=true` zwraca kopertę `{id, form, report}` (`trace`, `warnings`, `needs_review`, koszt, czas). `?editor=true` dokłada `editor` (`source` jako `ParsedDocument` i `field_map`).
- Kody: 400 (brak pliku, więcej niż jeden plik, zła nazwa), 401, 413, 415, 422, 502/504 (błąd lub timeout LLM).

## Konsekwencje
- Brak kolejki: żądanie trwa tyle, ile ekstrakcja. Limity `REQUEST_TIMEOUT_S` (300 s), `LLM_TIMEOUT_S` (60 s) i `MAX_PAGES` (30) chronią przed zawieszeniem, a #9 ma 16 stron.
- Identyfikator zapisanego formularza jest w kopercie z `?report=true`. Dla czystej odpowiedzi jest w nagłówku `Location` ([storage](../storage.md)).
- Postęp w tym samym żądaniu opisuje [0014](0014-postep-przez-sse.md).
