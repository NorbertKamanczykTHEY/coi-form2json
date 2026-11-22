# Wynikowe JSON-y do oddania

Formularze z pkt 4 treści zadania: #2, #3, #4, #6, #7, #8, #9. Każdy wynik to para plików: `*.coi.json` (JSON do importu w Generatorze Formularzy) i `*.report.json` (raport: `needs_review`, `warnings`, `proposed_dictionaries`, koszt, czas).

Pomiar EVAL-5 (HEAD `718fa0d`). Każdy plik przeszedł 3 razy, w `results/` leży przebieg mediany (kolumna „Przebieg”). Czas, pola i koszt dotyczą tego przebiegu. Źródło: [results/README.md](../../results/README.md).

| # | Formularz | JSON COI | Raport | Przebieg | Pola | needs_review | Czas [s] | Koszt [$] |
|---|---|---|---|---|---|---|---|---|
| 2 | Zwrot opłaty skarbowej (docx) | [2-zwrot-oplaty-skarbowej.coi.json](../../results/2-zwrot-oplaty-skarbowej.coi.json) | [report](../../results/2-zwrot-oplaty-skarbowej.report.json) | r3 | 57 | 3 | 35.5 | 0.01254 |
| 3 | Zaświadczenie (docx) | [3-zaswiadczenie.coi.json](../../results/3-zaswiadczenie.coi.json) | [report](../../results/3-zaswiadczenie.report.json) | r1 | 38 | 1 | 16.1 | 0.00368 |
| 4 | Świetlica (docx) | [4-swietlica.coi.json](../../results/4-swietlica.coi.json) | [report](../../results/4-swietlica.report.json) | r3 | 44 | 1 | 17.4 | 0.00209 |
| 6 | Pas drogowy (docx) | [6-pas-drogowy.coi.json](../../results/6-pas-drogowy.coi.json) | [report](../../results/6-pas-drogowy.report.json) | r3 | 85 | 4 | 72.2 | 0.01419 |
| 7 | Psy agresywne (doc) | [7-psy-agresywne.coi.json](../../results/7-psy-agresywne.coi.json) | [report](../../results/7-psy-agresywne.report.json) | r2 | 53 | 6 | 16.4 | 0.00395 |
| 7 | Psy agresywne, skan (jpg) | [7-psy-agresywne-skan.coi.json](../../results/7-psy-agresywne-skan.coi.json) | [report](../../results/7-psy-agresywne-skan.report.json) | r1 | 54 | 4 | 67.3 | 0.01617 |
| 8 | Deklaracja odpady (docx) | [8-deklaracja-odpady.coi.json](../../results/8-deklaracja-odpady.coi.json) | [report](../../results/8-deklaracja-odpady.report.json) | r1 | 93 | 6 | 33.0 | 0.06701 |
| 9 | Stypendium sportowe (docx) | [9-stypendium-sportowe.coi.json](../../results/9-stypendium-sportowe.coi.json) | [report](../../results/9-stypendium-sportowe.report.json) | r1 | 100 | 12 | 36.7 | 0.06736 |
| 9 | Stypendium sportowe, skan (png) | [9-stypendium-sportowe-skan.coi.json](../../results/9-stypendium-sportowe-skan.coi.json) | [report](../../results/9-stypendium-sportowe-skan.report.json) | r2 | 99 | 13 | 98.6 | 0.07155 |

- Wszystkie pliki przechodzą `POST /api/v1/forms/validate` i schemat z materiałów zadania.
- Ocena ekspercka każdego formularza: [results/eval-5/](../../results/eval-5/README.md).
- Wzorce #1 i #5 też są w `results/`, do porównania, nie do oddania.
- Uwaga do #8: przebieg mediany (r1, 93 pola) nie ma sekcji C i sekcji współmałżonka, które ma przebieg r3 (118 pól). Opis w [eval-5/README.md](../../results/eval-5/README.md), sekcja „Zmienność”.

Jak odtworzyć: z `app/backend` uruchom `PYTHONPATH=. uv run python ../results/run.py` przy działającym `docker compose up`.
