# Brief: dokumentacja projektu + przegląd kryteriów oceny

## Część A: przegląd wymagań i kryteriów (najpierw)
Źródła: `materials/COI - Pełna treść zadania konkursowego.pdf` (pkt 3.2, 3.3, 4, 5, 6, 8), `app/docs/requirements.md` (ID wymagań), ADR-y `app/docs/adr/`, `app/results/` (wyniki E2E i EVAL). Dla każdego wymagania (M*, R-*, T*, oddanie z pkt 4) ustal stan na bieżącym HEAD: spełnione, częściowo albo brak, z dowodem (plik, test, commit). Zapisz to w `app/docs/compliance.md` (tabela + lista luk z priorytetem). Sprawdzaj w kodzie, nie w dokumentach. Luki, które da się szybko zamknąć w dokumentacji albo konfiguracji, zamykasz sam. Luki w kodzie opisz w raporcie (nie naprawiaj).

## Część B: dokumentacja w repozytorium (`app/`)
Wymagana przez pkt 5 i 3.2.II:
- **`app/README.md`** (główny): czym jest rozwiązanie; szybki start (`docker compose up`); **budowanie obrazów** (backend, frontend); **uruchomienie**; **konfiguracja** (tabela wszystkich zmiennych env z domyślnymi wartościami; pakiet `coi/config/`); **opis REST API** (endpointy, kody, SSE, JWT, przykłady curl, link do `/docs`); tryb air gap; tokeny do demo (`make_token`).
- **`app/docs/architecture.md`**: dokumentacja architektury: kontekst, kontenery, przepływ `parse → extract → generate → validate`, drabina eskalacji i bramki, kontrakty (`ParsedDocument`, `FieldTree`, JSON COI), magazyn (SQLAlchemy/SQLite), bezpieczeństwo (pliki tylko w pamięci, JWT, sekrety w runtime, non-root, porty), koszt na formularz (z `app/results/`), ograniczenia. Diagramy w Mermaid. Linki do ADR-ów przy każdej decyzji.
- **Wymagania obowiązkowe i decyzje architektoniczne** mają być wprost nazwane i odhaczone (odsyłacz do `compliance.md`).
- **Prompty są osobno i łatwo je konfigurować**: wszystkie w `coi/prompts/*.md`, kod je tylko wczytuje. Opisz, jak dostosować prompt do wymagań urzędu bez zmiany kodu, oraz drabiny modeli w plikach JSON (`ladder.json`, ustawienia ekstrakcji).
- Przenieś do `app/docs/` to, co jest potrzebne z dokumentów spoza repo (`/Users/bert/Hacknation/coi_formularze/docs/superpowers/specs/2026-11-21-parser-contract-design.md`, istotne części `research/2026-11-21-flow-review.md`: scenariusze, role osób, decyzje mentorów), aktualizując nieaktualne miejsca (PaddleOCR → Eden VLM, `DB_PATH` → `DATABASE_URL`).
- Zaktualizuj nieaktualne dokumenty w `app/docs/` (`api-assumptions.md`, `storage.md` itd.) albo oznacz je jako historyczne.

## Zasady
- Pisz po polsku, zwięźle, bez lania wody. Linkuj zamiast powtarzać.
- Nie zmieniaj kodu (poza poprawkami w README i plikach `.env.example`, jeśli są niezgodne z kodem).
- Komendy z README sprawdź w praktyce (build obrazów, `docker compose up`, curl na `/healthz` i jednym pliku), potem zamknij kontenery.
- Commituj tylko `app/README.md`, `app/docs/**` i ewentualnie `.env.example`, podając ścieżki. Nie pushuj.

## Raport
Tabela zgodności (skrót), lista luk w kodzie z priorytetem, lista utworzonych i zmienionych plików, wynik sprawdzenia komend.
