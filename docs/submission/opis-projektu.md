# Blankiet → e-usługa: formularz urzędowy w JSON COI w kilka minut

**Podtytuł:** usługa REST, która zamienia jeden plik blankietu (PDF, DOC, DOCX, ODS, XLSX, JPG, PNG) na JSON gotowy do importu w Generatorze Formularzy COI. Za formularz płaci się średnio około 2 centy.

## Problem

Urzędnik, który cyfryzuje e-usługę, ma papierowy wniosek: plik Worda, PDF albo skan. Musi go ręcznie przenieść do Generatora Formularzy: rozpisać strony, sekcje i pola, wybrać walidatory i słowniki, ustawić zależności („pokaż, jeśli zaznaczono…”) i pilnować Standardów COI. Przy formularzu takim jak #9 (stypendium, 151 pól, trzy wnioski w jednym) to godziny pracy i spore ryzyko pomyłki.

## Rozwiązanie

Jedno wywołanie `POST /api/v1/forms` z plikiem zwraca JSON COI i raport. Przepływ: `parse → extract → generate → validate`.

1. **parse**: tekst wyciągamy lokalnie (Kreuzberg, Tesseract `pol`). Model wizyjny dostaje tylko te strony skanu, które odrzuci bramka jakości.
2. **extract**: LLM buduje `FieldTree`, czyli pola przedmiotu wniosku z kotwicą w źródle. Bramka (Pydantic i reguły G1–G17) odrzuca złe wyniki i uruchamia naprawę albo mocniejszy model.
3. **generate**: deterministycznie, bez LLM. Szablony stron „Dane”, „Kontakt i zgody” i strony końcowej według wzorców #1 i #5, słowniki z katalogu, walidatory z etykiet, `states` SHOW w JSONata.
4. **validate**: schemat JSON z zadania, reguły R1–R6, unikalne `techName`, poprawność odwołań JSONata.

Frontend: wczytanie kilku plików naraz, postęp na żywo (SSE), podgląd JSON-a, podgląd e-usługi (strony, sekcje, SHOW), raport pól do sprawdzenia z mapą źródła, edycja i zapis. TODO(screenshot): zrzut nowego frontu (shadcn).

Źródła: [README.md](../../README.md), [architecture.md](../architecture.md).

## Zakres minimalny i rozszerzenia

Pełna tabela z dowodami jest w [compliance.md](../compliance.md).

| Wymaganie | Jak spełniamy | Stan |
|---|---|---|
| M1: formaty PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG | `coi/parsing/detect.py`: rozszerzenie i magic bytes muszą się zgadzać, inaczej 415 | ✅ |
| M2, M3: JSON zgodny z treścią, schematem i wzorcami #1, #5 | 11 z 11 plików przechodzi walidację ([results/README.md](../../results/README.md)); EVAL-3: #1 i #5 bez rozbieżności krytycznych | ✅ |
| M4: zasady projektowania (Standardy, Reguły techniczne) | Strony tematyczne z szablonów, pola domyślnie wymagane ([ADR 0018](../adr/0018-pola-domyslnie-wymagane.md)). EVAL-3: 22 rozbieżności krytyczne w #2–#9. TODO(EVAL-4): wynik po regułach G1–G17 | 🟡 |
| M5: dokumentacja architektury | [architecture.md](../architecture.md), 27 ADR-ów | ✅ |
| I: słowniki i dane inicjalne | Katalog słowników (Kraje, TERYT, województwa, powiaty, gminy, miejscowości), dopasowanie po etykiecie i opcjach, `defaultValue: "MLPZ.*"` | ✅ |
| II: propozycja nowego słownika | `report.proposed_dictionaries` (#5, #7, #9), przyjęcie przez `POST /api/v1/dictionaries/from-proposal` | ✅ |
| III: zależności i dynamiczne przepływy | 438 warunków `states` SHOW w JSONata w wynikach, `$repeatingSectionIndex` w sekcjach powtarzalnych. Przejścia między stronami są liniowe, bo schemat nie ma warunków w `flow.links` | 🟡 |
| IV: frontend do wczytania i przeglądu | Upload kilku plików, postęp SSE, JSON, raport, historia, zapis, regeneracja | ✅ |
| V: wizualizacja jako e-usługa | `Preview.tsx`: strony, sekcje, sekcje powtarzalne, słowniki, SHOW liczony przez `jsonata` | ✅ |
| VI: walidacje i UX | Walidatory z etykiet: REQUIRED, ZIP_CODE, EMAIL, NIP, REGON, PESEL, EPUAP, ADE, SERIAL_NUMBER_ID_CARD; batch z kolejką. Brak walidatora telefonu (schemat zadania nie ma takiej nazwy) | 🟡 |

## Architektura w skrócie

- Dwa kontenery, każdy z własnym Dockerfile: `backend` (Flask/APIFlask, gunicorn, Python 3.14, Kreuzberg, Tesseract) i `frontend` (Vite, React, shadcn/ui, nginx bez roota). Wersje obrazów przypięte, procesy bez roota ([ADR 0003](../adr/0003-kontener-na-modul.md)).
- Jedno publiczne API REST, opis OpenAPI 3.1 i Swagger UI pod `/docs`. Błędy w formacie RFC 9457 ([ADR 0016](../adr/0016-bledy-rfc-9457-openapi-batch-we-froncie.md)).
- Dwa kontrakty między modułami: `ParsedDocument` (wynik parsera) i `FieldTree` (wynik ekstrakcji, wejście generatora). Generator nie zna numeru formularza; reguły wynikają z treści ([ADR 0024](../adr/0024-uniwersalne-reguly-bez-poprawek-pod-formularz.md)).
- Plik istnieje tylko w pamięci na czas żądania. W bazie zostaje wynik, nazwa i sha256 pliku ([storage.md](../storage.md)).
- 261 testów (`uv run pytest -m "not eden"`), bez sieci ([compliance.md](../compliance.md)).

## Koszt i czas na formularz

Przebieg E2E na docker compose, 11 plików ([results/README.md](../../results/README.md)):

| Formularz | Format | Pola | Czas [s] | Koszt [$] |
|---|---|---|---|---|
| #3 zaświadczenie (najprostszy) | docx | 36 | 4.6 | 0.0014 |
| #1 numer porządkowy (wzorzec) | docx | 53 | 10.1 | 0.0032 |
| #6 pas drogowy | docx | 70 | 69.2 | 0.0145 |
| #8 deklaracja odpady | docx | 120 | 184.5 | 0.0573 |
| #9 stypendium (3 wnioski w 1) | docx | 151 | 224.7 | 0.0666 |
| #7 skan | jpg | 46 | 60.1 | 0.0097 |
| #9 skan | png | 144 | 171.2 | 0.0599 |

Cały przebieg kosztował **$0.2467**, czyli średnio około 2 centy na formularz. W trybie `LLM_PROVIDER=local` koszt API wynosi zero (płaci się tylko za GPU). TODO(EVAL-4): podmienić na liczby z `results/eval-4/`.

## Potencjał wdrożeniowy

- **Air gap:** `LLM_PROVIDER=local` i `LLM_BASE_URL` wskazujące Ollamę albo vLLM w sieci urzędu. Aplikacja nie wysyła wtedy nic na zewnątrz; sprawdza to test `tests/parsing/test_airgap.py` ([ADR 0010](../adr/0010-adapter-dostawcy-modeli-i-air-gap.md)). Parsowanie zawsze działa w kontenerze.
- **Logowanie urzędu:** backend tylko weryfikuje JWT. HS256 albo RS256 z kluczami z JWKS IdP, z kontrolą `iss`, `aud` i `exp` ([ADR 0015](../adr/0015-jwt-tylko-weryfikacja.md)).
- **Baza:** SQLAlchemy 2. SQLite na wolumenie albo PostgreSQL przez samą zmianę `DATABASE_URL` ([ADR 0017](../adr/0017-sqlite-za-sqlalchemy.md)).
- **Dostosowanie bez programisty:** prompty to pliki `.md` w `coi/prompts/`, które można podmontować jako wolumen. Drabiny modeli są w `ladder.json` i `EXTRACTION_LADDER`. Szablony stron i słowniki zmienia się bez wdrożenia ([architecture.md, Dostosowanie bez zmiany kodu](../architecture.md#dostosowanie-bez-zmiany-kodu)).
- **Integracja:** to samo API obsłuży front, system COI i agenta AI (np. AI HUB). SSE pokazuje postęp, a `?report=true` zwraca raport do przeglądu.

## Oryginalność

- **Drabina eskalacji z bramką jakości.** Najtańszy krok idzie pierwszy, a droższy model startuje tylko wtedy, gdy kod odrzuci wynik. Przy skanach Tesseract jest świadkiem: VLM, który „zmyśla” tekst, przegrywa porównanie pokrycia słów ([ADR 0008](../adr/0008-drabina-eskalacji-z-bramka.md), [ADR 0007](../adr/0007-t0-lokalnie-skany-do-vlm.md)).
- **Edytor z mapą źródła i `needs_review`.** Każde pole wie, z której strony i z którego bloku papieru pochodzi. Pola wątpliwe trafiają do raportu z odnośnikiem do źródła, a po poprawkach formularz przebudowuje się bez ponownego LLM (`/regenerate`, [ADR 0027](../adr/0027-tylko-osobiscie-i-regeneracja.md)).
- **Zero cichych porażek.** Każdy problem trafia do odpowiedzi: błąd RFC 9457, `warning`, `escalation` w SSE albo pozycja `needs_review`. Timeout modelu liczy się jako nieudany szczebel drabiny, a nie jako błąd żądania.
- **Słowniki tylko z dowodem.** Nowy słownik proponujemy tylko wtedy, gdy dokument daje listę pozycji, a JSON COI zawiera wyłącznie słowniki istniejące ([ADR 0021](../adr/0021-nowy-slownik-tylko-z-lista-pozycji.md), [ADR 0025](../adr/0025-propozycje-slownikow-tylko-w-raporcie.md)).

## Ograniczenia

- Żądanie jest synchroniczne: #8 i #9 trwają 3–4 minuty ([ADR 0013](../adr/0013-post-forms-synchronicznie.md)).
- Dokumenty biurowe nie mają obrazu strony, więc nie eskalują do VLM.
- Tryb air gap nie był uruchomiony end-to-end na prawdziwym modelu lokalnym dla pełnego zestawu ([compliance.md](../compliance.md), T3).
