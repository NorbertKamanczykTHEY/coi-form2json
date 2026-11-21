# Brief: EVAL-3, wszystkie formularze kontra interpretacja eksperta (tylko porównanie)

## Cel
Przepuścić wszystkie formularze przez bieżący HEAD i porównać każdy wynikowy JSON z tym, jak doświadczony projektant e-usług (ty) zinterpretowałby formularz źródłowy według materiałów COI. **Niczego nie poprawiasz w kodzie.** Wynikiem jest lista rozbieżności i ogólnych reguł do wdrożenia. Poprawki wdrożą inne wątki.

## Krok 1: przebieg
- Z `app/backend`: `uv run python ../results/run.py` na docker compose (zob. `app/results/README.md`). Uwzględnij wszystkie formularze #1–#9 i skany (#7 jpg, #9 png). Zaktualizuj `app/results/` (README, summary.json, *.coi.json, *.report.json).

## Krok 2: interpretacja wzorcowa i porównanie (na każdy formularz)
Źródła prawdy (czytaj): plik formularza w `/Users/bert/Hacknation/coi_formularze/materials/<n>.*/`, „HackNation - Standardy i dobre praktyki projektowania formularzy.pdf”, „Reguły techniczne…docx”, „Słowniki”, „Dane inicjalne” (`materials/Materiały do zadania dla Uczestników/`), wzorce #1 i #5 (papier + oczekiwany JSON), `research/2026-11-21-flow-review.md` (S1–S17, decyzje mentorów) i ADR-y w `app/docs/adr/`.
Dla każdego formularza najpierw zapisz własną krótką interpretację: strony, sekcje, pola (typ, wymagalność, opcje, słownik, walidator), zależności SHOW, sekcje powtarzalne i zgody. Dopiero potem porównaj ją z `app/results/<n>.coi.json`. Rozbieżności sklasyfikuj:
- **Brak / nadmiar pola**, **zły typ**, **zła wymagalność**, **brak lub zła zależność**, **zły podział na strony lub sekcje**, **słownik lub walidator**, **treść** (tytuł, etykieta, opis, język).
- Waga: krytyczna (urzędnik musiałby poprawić, a obywatel nie złoży wniosku albo poda złe dane), średnia, kosmetyczna.
- Każda rozbieżność ma: plik źródłowy i stronę, fragment źródła, co jest w JSON, co powinno być.

## Krok 3: reguły ogólne
Pogrupuj rozbieżności w **reguły ogólne**, które wynikają z treści formularza, a nie z jego numeru (np. „pole przy opcji »inne« → TEXT_FIELD ze SHOW”). Przy każdej regule: na których formularzach występuje, gdzie ją wdrożyć (prompt ekstrakcji, bramka, generator, szablon), szacowany zysk. Odrzuć poprawki pasujące tylko do jednego formularza, chyba że wynikają z ogólnej zasady ze Standardów.

## Wynik
- `app/results/eval-3/<n>.md` na każdy formularz oraz `app/results/eval-3/README.md` z tabelą: formularz → liczba rozbieżności według wagi, i z listą reguł ogólnych posortowaną po zysku.
- Commit tylko `app/results/` (podając ścieżki). Nie pushuj.

## Zasady
- Nie edytuj `app/backend/` ani `app/frontend/`.
- Koszt Eden przebiegu podaj w raporcie.
- Pytania do użytkownika o formularz zawsze z plikiem i stroną źródła.
