# Brief: przebudowa interfejsu (frontend)

Najpierw wywołaj skill `/frontend-design` i pracuj według niego. Front: `app/frontend/` (Vite + React + TS + shadcn/ui, ADR 0001). Obecny stan: `src/App.tsx`, `src/Preview.tsx`, typy z OpenAPI w `src/api.d.ts`. Kontekst poprzedniego wątku frontu: `ghostex read-session-chat S0j:P0jqk:G076u --last 10 --format text`. API: `app/backend/README.md`, Swagger `/docs`. Użytkownik to urzędnik cyfryzujący formularze. Liczą się intuicyjność (20% oceny) i porządny wygląd.

## Wymagania użytkownika (podyktowane, oddany sens)
1. **Ekran główny = lista projektów**, czyli formularzy zapisanych w SQLite (`GET /api/v1/forms`): tytuł, plik źródłowy, data, liczba wątpliwości, propozycje słowników, oznaczenie „nowe” dla elementów dodanych w tej sesji.
2. **Usuwanie projektu** z modalem potwierdzenia. Backend nie ma `DELETE /api/v1/forms/{id}`, więc dodaj go w `coi/api.py` (JWT, 204/404, problem+json, test w `tests/api`).
3. **Widok projektu (edytor):**
   - akceptacja proponowanych słowników (`POST /dictionaries/from-proposal`);
   - rozwiązywanie wątpliwości (`needs_review`): **czerwona kropka przy każdej stronie (zakładce), która ma nierozwiązane uwagi**, oraz **wyraźne czerwone oznaczenie pola**, które wymaga decyzji urzędnika (obramowanie, ikona, powód). Rozwiązanie uwagi = poprawka pola albo „akceptuję”. Stan rozwiązania musi się zapisywać na serwerze: rozszerz `PUT /forms/{id}` o listę rozwiązanych pozycji albo dodaj osobny endpoint, z testem;
   - edycja pól zmienia JSON formularza (`PUT /forms/{id}` z walidacją).
4. **Makieta formularza**, czyli widok obywatela, renderowana z bieżącego JSON (także po edycji): strony jako kroki, siatka x/y, typy pól, działające SHOW (jsonata), sekcje powtarzalne, zgody. Rozwiń obecny `Preview.tsx`.
5. **Górna belka:**
   - **Podgląd JSON:** modal z uploadem pliku `.json` albo polem do wklejenia treści, który otwiera makietę dowolnego JSON-a COI (bez zapisu).
   - **Import plików:** modal uploadu. Pliki można dodawać grupami do istniejącej kolejki.
6. **Kolejka importu:**
   - działa w tle, niezależnie od modala, i przetwarza N plików naraz (stała w konfiguracji frontu, np. 2);
   - walidacja po stronie klienta (rozszerzenie, nazwa ≤ 250 znaków bez `; : > < / \ | ' * % $`, rozmiar z `/api/v1/info`). Plik niespełniający wymagań, odrzucony przez API (400/413/415/422) albo z błędem jest oznaczony jako odrzucony, z powodem;
   - element kolejki to wiersz z rozwijaną strzałką. Po rozwinięciu widać ładnie sformatowany log zdarzeń SSE (etapy, eskalacje, ostrzeżenia, koszt, czas) zamiast surowego JSON-a;
   - element zakończony dostaje ikonę „gotowe”;
   - w trakcie pracy kolejki zamknięcie lub odświeżenie karty ostrzega (`beforeunload`). Po zakończeniu można zamknąć modal, a nowe projekty pojawiają się na liście z oznaczeniem „nowe”.
7. Token JWT: jak dotąd wklejany (ADR 0015), bez logowania.

## Zasady
- Komponenty shadcn/ui, spójny system wizualny, dostępność (fokus, aria, kontrast), poprawny widok na szerokości laptopa i tabletu.
- Typy z OpenAPI przegeneruj po zmianach backendu.
- Nie zmieniaj logiki `coi/extraction`, `coi/generator`, `coi/parsing`. W backendzie tylko endpointy wymienione wyżej, z testami.
- Serwery dev uruchamiaj na czas pracy i zamykaj na koniec.
- Commituj tylko swoje pliki, podając ścieżki. Nie pushuj.

## Dowód
`npm run build` i lint przechodzą. `uv run pytest -m "not eden"` przechodzi. Test Playwright przeprowadza: import 3 plików z `materials/`, w tym jednego złego (np. `.JPE`), rozwinięcie logu, listę z „nowe”, edytor z czerwonymi oznaczeniami, rozwiązanie jednej uwagi (kropka znika po zapisie), makietę ze SHOW, podgląd wklejonego JSON-a i usunięcie z potwierdzeniem. Zrzuty ekranu podaj w raporcie jako ścieżki PNG.
