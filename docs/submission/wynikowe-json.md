# Wynikowe JSON-y do oddania

Formularze z pkt 4 treści zadania: #2, #3, #4, #6, #7, #8, #9. Każdy wynik to para plików: `*.coi.json` (JSON do importu w Generatorze Formularzy) i `*.report.json` (raport: `needs_review`, `warnings`, `proposed_dictionaries`, koszt, czas).

TODO(EVAL-4): pliki w `results/` pochodzą z obrazu HEAD `c935629`. Po EVAL-4 podmienić na wyniki z `results/eval-4/` (albo zaktualizowane `results/`) i przepisać kolumny Pola, Czas i Koszt.

| # | Formularz | JSON COI | Raport | Pola | Czas [s] | Koszt [$] |
|---|---|---|---|---|---|---|
| 2 | Zwrot opłaty skarbowej (docx) | [2-zwrot-oplaty-skarbowej.coi.json](../../results/2-zwrot-oplaty-skarbowej.coi.json) | [report](../../results/2-zwrot-oplaty-skarbowej.report.json) | 66 | 51.0 | 0.01735 |
| 3 | Zaświadczenie (docx) | [3-zaswiadczenie.coi.json](../../results/3-zaswiadczenie.coi.json) | [report](../../results/3-zaswiadczenie.report.json) | 36 | 4.6 | 0.00137 |
| 4 | Świetlica (docx) | [4-swietlica.coi.json](../../results/4-swietlica.coi.json) | [report](../../results/4-swietlica.report.json) | 43 | 45.2 | 0.00946 |
| 6 | Pas drogowy (docx) | [6-pas-drogowy.coi.json](../../results/6-pas-drogowy.coi.json) | [report](../../results/6-pas-drogowy.report.json) | 70 | 69.2 | 0.01453 |
| 7 | Psy agresywne (doc) | [7-psy-agresywne.coi.json](../../results/7-psy-agresywne.coi.json) | [report](../../results/7-psy-agresywne.report.json) | 41 | 19.3 | 0.00351 |
| 7 | Psy agresywne, skan (jpg) | [7-psy-agresywne-skan.coi.json](../../results/7-psy-agresywne-skan.coi.json) | [report](../../results/7-psy-agresywne-skan.report.json) | 46 | 60.1 | 0.00974 |
| 8 | Deklaracja odpady (docx) | [8-deklaracja-odpady.coi.json](../../results/8-deklaracja-odpady.coi.json) | [report](../../results/8-deklaracja-odpady.report.json) | 120 | 184.5 | 0.05729 |
| 9 | Stypendium sportowe (docx) | [9-stypendium-sportowe.coi.json](../../results/9-stypendium-sportowe.coi.json) | [report](../../results/9-stypendium-sportowe.report.json) | 151 | 224.7 | 0.06655 |
| 9 | Stypendium sportowe, skan (png) | [9-stypendium-sportowe-skan.coi.json](../../results/9-stypendium-sportowe-skan.coi.json) | [report](../../results/9-stypendium-sportowe-skan.report.json) | 144 | 171.2 | 0.05994 |

Źródło liczb: [results/README.md](../../results/README.md). Wszystkie pliki przechodzą `POST /api/v1/forms/validate` i schemat z materiałów zadania. Wzorce #1 i #5 też są w `results/` (do porównania, nie do oddania).

Jak odtworzyć: z `app/backend` uruchom `PYTHONPATH=. uv run python ../results/run.py` przy działającym `docker compose up`.
