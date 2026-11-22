# Brief: edycja w podglądzie, edytor warunków JSONata, kolejka w tle (nowy branch)

Pracujesz na osobnym branchu w swoim worktree (Ghostex go utworzył). Nazwij branch `feature/preview-editor`, jeśli nazwa jest inna. Front: `app/frontend/` (Vite + React + TS + shadcn/ui). Kontekst poprzedniego wątku frontu: `ghostex read-session-chat S0j:P0jqk:G1cov --last 8 --format text`; README frontu: `app/frontend/README.md`. Najpierw wywołaj skill `/frontend-design`.

## Zadania (od użytkownika)
1. **Edycja formularza w widoku podglądu (makieta dla obywatela).** Urzędnik edytuje formularz wprost na makiecie: etykiety, opisy, wymagalność, opcje i kolejność pól, z dodawaniem i usuwaniem pól i sekcji. Zmiany idą do tego samego JSON-a co w edytorze „Pola i uwagi”, a zapis przez istniejące `PUT /api/v1/forms/{id}` z walidacją. Tryb przełączany „Podgląd / Edycja”. W trybie podglądu makieta działa jak dla obywatela.
2. **Sekcje i pola z JSONata (`states` SHOW/READ_ONLY)** dostają w makiecie i w edytorze widoczne oznaczenie (ikona i krótki opis warunku po ludzku) oraz przycisk „Edytuj warunek”. Otwiera się modal z dwiema zakładkami:
   - **Tekst:** wyrażenie JSONata z walidacją na żywo (składnia przez bibliotekę `jsonata`, odwołania do istniejących stron i techName z JSON-a). Błędy pokazane przy wyrażeniu.
   - **Graficzny:** konstruktor warunku: pole sterujące (lista pól wyboru z formularza), operator (jest / nie jest jedną z), opcje, łączenie AND/OR, negacja. Zmiana w konstruktorze **od razu modyfikuje tekst**. Generuj wyrażenia w tej samej formie co generator i wzorce, np. `("Innej osoby" in tabs['Dane' in title].questions[...].field.repeatingSectionGrid['<techName>' in field.techName].field.__userAnswer)` i `$not(...)`. Wzór: `app/docs/design/generator.md` (JSONata) i JSON-y w `app/results/`. Gdy tekstu nie da się odwzorować graficznie, zakładka graficzna mówi to wprost, a tekst zostaje edytowalny.
   - Akcje: **Zapisz** (tylko poprawne wyrażenie) i **Anuluj**.
3. **Upload i przetwarzanie plików w tle:** modal importu można zamknąć, a kolejka pracuje dalej. Element menu „Importuj pliki” pokazuje stan (licznik albo spinner w toku, znak zakończenia lub błędu). Ponowne kliknięcie przywraca ten sam modal z bieżącym stanem kolejki. Blokada zamknięcia karty (`beforeunload`) działa, dopóki kolejka pracuje w tle. Sprawdź, co już jest, i dokończ brakujące części.

## Zasady
- Bez zmian w `coi/extraction`, `coi/generator`, `coi/parsing`. Jeśli potrzebny jest nowy endpoint, dodaj go w `coi/api.py` z testem.
- Dostępność (fokus w modalach, aria, klawiatura), spójność z istniejącym systemem wizualnym, polska odmiana (`lib/plural.ts`).
- Serwery dev uruchamiaj na czas pracy i zamykaj na koniec. Używaj kopii bazy w scratchpadzie.
- Commituj na swoim branchu, bez pusha i bez merge'a do master.

## Dowód
`npm run build` i lint przechodzą. Jeśli ruszałeś backend, `uv run pytest -m "not eden"` przechodzi. Test Playwright: edycja etykiety w makiecie z zapisem i odświeżeniem; warunek edytowany graficznie zmienia tekst, zapis i działanie SHOW w makiecie; błędny tekst blokuje zapis; zamknięcie modala importu w trakcie, znacznik w menu, ponowne otwarcie ze stanem. Zrzuty PNG z podaniem ścieżek.
