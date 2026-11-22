# Brief: materiały do oddania (opis, prezentacja, scenariusz filmu)

Wymagania z pkt 4 treści zadania (`materials/COI - Pełna treść zadania konkursowego.pdf`): szczegółowy opis i tytuł projektu, prezentacja PDF do 10 slajdów, wynikowe pliki JSON, film do 3 minut, repozytorium, opcjonalnie zrzuty ekranu. Kryteria oceny (pkt 8): kompletność 30%, intuicyjność 20%, jakość kodu 20%, potencjał wdrożeniowy z kosztem 20%, oryginalność 10%.

Źródła: `app/README.md`, `app/docs/architecture.md`, `app/docs/compliance.md`, ADR-y, `app/results/` (koszty, czasy; po EVAL-4 pojawi się `app/results/eval-4/`), `app/docs/design/*`.

## Do zrobienia (w `app/docs/submission/`)
1. **`opis-projektu.md`**: tytuł (krótki, chwytliwy) i szczegółowy opis: problem, rozwiązanie, jak spełnia minimum i rozszerzenia I–VI, architektura w skrócie, koszt na formularz, potencjał wdrożeniowy (air gap, IdP/JWKS, ORM, prompty w plikach `.md` łatwe do dostosowania, drabina modeli w konfiguracji), oryginalność (drabina eskalacji z bramką jakości, edytor z mapą źródła i `needs_review`, zero cichych porażek).
2. **Prezentacja**: maksymalnie 10 slajdów, jako PDF. Źródło w HTML lub Markdown (np. Marp: `npx @marp-team/marp-cli --pdf`, licencja MIT), PDF w `app/docs/submission/prezentacja.pdf`. Slajdy nastawione na kryteria oceny. Liczby z `app/results/` (czasy, koszty, wynik walidacji, EVAL). Diagram architektury.
3. **`scenariusz-filmu.md`**: scenariusz filmu do 3 minut (ujęcia, czas, co mówimy, co klikamy we froncie). Nagranie robi użytkownik.
4. **Lista wynikowych JSON-ów do oddania** (#2, #3, #4, #6, #7, #8, #9) z odnośnikami do `app/results/`.

## Zasady
- Po polsku, konkretnie, bez marketingowego lania wody. Każda liczba ma źródło w repozytorium.
- Miejsca zależne od EVAL-4 lub nowego frontu oznacz `TODO(EVAL-4)` / `TODO(screenshot)`. Uzupełnię je po wynikach.
- Commit tylko `app/docs/submission/`, podając ścieżki. Nie pushuj.

## Raport
Lista plików, ścieżka do PDF, liczba slajdów, lista TODO.
