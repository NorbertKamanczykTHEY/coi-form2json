# Brief: ADR-y w app/docs/adr/

## Cel
Zapisać decyzje projektu jako ADR-y w `/Users/bert/Hacknation/coi_formularze/app/docs/adr/`, w formacie krótkiego Nygarda, po polsku. Plik `NNNN-tytul-kebab.md` zawiera:
```
# NNNN. Tytuł
Data: 2026-11-21 · Status: przyjęta | proponowana
Źródło: SPEC (<ID z app/docs/requirements.md, np. T5>) | MENTORZY | ZESPÓŁ
## Kontekst
## Decyzja
## Konsekwencje
```
Do tego `app/docs/adr/README.md` z tabelą: nr, tytuł, status, źródło, link. **Oznacz, które ADR-y wynikają ze specyfikacji zadania** (Źródło: SPEC z ID wymagania z `app/docs/requirements.md`). Jeśli decyzja wynika ze specyfikacji tylko częściowo, wpisz oba źródła, np. „SPEC (T3) + ZESPÓŁ”, i w Kontekście napisz, co jest wymogiem, a co naszym wyborem.

## Źródła (czytaj przed pisaniem, nie wymyślaj uzasadnień)
- `/Users/bert/Hacknation/coi_formularze/app/docs/requirements.md` (ID wymagań)
- `/Users/bert/Hacknation/coi_formularze/app/docs/api-assumptions.md`
- `/Users/bert/Hacknation/coi_formularze/docs/superpowers/specs/2026-11-21-parser-contract-design.md`
- `/Users/bert/Hacknation/coi_formularze/poc-1-ocr/research/gate-design.md`, `/Users/bert/Hacknation/coi_formularze/poc-1-ocr/RESULTS.md`
- `/Users/bert/Hacknation/coi_formularze/research/2026-11-21-flow-review.md` (odpowiedzi mentorów, S/U/P/R)
- `/Users/bert/Hacknation/coi_formularze/app/docs/design/generator.md`, `/Users/bert/Hacknation/coi_formularze/app/docs/storage.md`
- `/Users/bert/Hacknation/coi_formularze/HANDOFF.md`

## Lista decyzji (zatwierdzona przez użytkownika, z jego poprawkami)
1. Monorepo `app/`: backend Flask (APIFlask), frontend Vite + React + shadcn (wybrany, bo dobrze udokumentowany). Repo git tylko w `app/`.
2. Python 3.14 + uv. Licencje bez copyleftu (wykluczone PyMuPDF, Ghostscript, GPL).
3. Każdy moduł (front, back, ewentualnie Kreuzberg) ma własny Dockerfile i działa jako osobny kontener. Obrazy oficjalne i lekkie, wersje jawne, użytkownik bez roota, sekrety w runtime.
4. Jedno publiczne API. Usługi pomocnicze działają w sieci wewnętrznej compose i nie publikują portów.
5. Mapa typ pliku → parsery w konfiguracji, z fallbackiem. Wspólny kontrakt `ParsedDocument` (strony → bloki). Znaczniki `☐` / `___` normalizuje adapter.
6. Wykrywanie typu: rozszerzenie bez względu na wielkość liter + **MIME z magic bytes porównany z rozszerzeniem** (wymóg). `.DOC` z docx w środku przyjmujemy jako docx, `.JPE` odrzucamy.
7. T0 lokalnie: Kreuzberg + Tesseract `pol` dla PDF, DOC i XLSX. Skany i obrazy idą do VLM. PaddleOCR odpada.
8. Drabina eskalacji z bramką jakości: szczeble modeli w `ladder.json` (podmiana przez config). „Nie zawodzimy po cichu”: `trace[]`, `needs_review`.
9. Serwis parsowania kończy się na `ParsedDocument`. Ekstrakcja pól to osobny krok.
10. **Modele (LLM i VLM) za osobnym adapterem dostawcy, łatwym do podmiany.** Eden AI (decyzja mentorów, modele z otwartymi wagami) to jedna implementacja. Te same modele mogą działać całkowicie lokalnie (vLLM, Ollama). **Musi być możliwa praca w trybie air gap**, bez ruchu wychodzącego. Opisz, jak przełączyć dostawcę i co działa offline.
11. Sekrety (klucz Eden, JWT) tylko w `.env` i zmiennych środowiskowych, nigdy w kodzie ani logach. W trybie air gap klucz Eden nie jest potrzebny.
12. Decyzja „istniejący słownik / nowy / bez słownika” zapada modelem klasyfikacyjnym z otwartymi wagami, jeśli taki istnieje. W przeciwnym razie LLM albo rapidfuzz. Status: proponowana (wątek słowników jeszcze wybiera).
13. `POST /api/v1/forms`: jeden plik, odpowiedź synchroniczna. Domyślnie czysty JSON COI, `?report=true` dodaje raport, `?editor=true` źródło i `field_map`.
14. Postęp przez SSE w tym samym żądaniu, bez kolejki zadań.
15. JWT: API tylko weryfikuje (HS256 albo JWKS), konfiguracja w `.env`, bez endpointu logowania, front przyjmuje wklejony token.
16. Błędy w formacie RFC 9457. OpenAPI i Swagger z APIFlask. Batch robi frontend.
17. **Baza: SQLite na wolumenie w MVP, za warstwą ORM (SQLAlchemy), żeby na produkcji przełączyć na inną bazę samym `DATABASE_URL`.** Przechowujemy formularze wynikowe i słowniki, a edycja odbywa się przez endpointy. Przesłanego pliku nie zapisujemy. MVP: każdy uwierzytelniony użytkownik widzi wszystko.
18. Pola są domyślnie wymagane. Opcjonalne tylko przy wyraźnym znaczniku albo przy „można dołączyć”.
19. Bez pól wyliczanych, bo JSONata zwraca tylko true/false. Wzór pokazujemy w opisie.
20. #9 to jeden formularz: radio „rodzaj wniosku” + sekcje ze SHOW. Flow liniowy.
21. Nowy słownik tylko wtedy, gdy mamy listę pozycji. Propozycja trafia do `proposed_dictionaries` i można ją przyjąć przez endpoint.
22. Dane inicjalne tylko konfigurujemy (źródło + atrybut), niczego nie wypełniamy. Status: proponowana (MLPZ kontra PESEL u mentorów).
23. Przy rozbieżności schematu i wzorców trzymamy się wzorców #1/#5 (np. `repeatingSectionGrid`). Status: proponowana.

## Granice
- Piszesz tylko w `app/docs/adr/`. Nie zmieniasz kodu.
- Zwięźle: ADR ma 10–25 linii. Nie powtarzaj całych dokumentów, linkuj do nich.
- Commituj tylko `app/docs/adr/`, podając ścieżki (`git add app/docs/adr`). Nie pushuj.

## Raport
Tabela z README (nr, tytuł, status, źródło) i lista miejsc, w których źródła są ze sobą sprzeczne albo decyzja nie ma oparcia w dokumentach.
