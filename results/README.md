# Wyniki E2E (docker compose, POST /api/v1/forms?report=true)

Kod: obraz z HEAD 718fa0d (pomiar końcowy EVAL-5). Każdy plik przeszedł 3 razy, **sekwencyjnie** (bez równoległych żądań, czasy są prawdziwe). Tu leży **przebieg mediany** (kolumna „Przebieg”: mediana liczby pól, przy remisie needs_review, potem niższy koszt). Zmienność i czasy 3 przebiegów: [eval-5/zmiennosc.md](eval-5/zmiennosc.md), ocena ekspercka: [eval-5/README.md](eval-5/README.md).

Skrypt: `run.py` (z app/backend: `PYTHONPATH=. uv run python ../results/run.py`). Walidacja: `POST /forms/validate` i schemat z `materials/`.

| Plik | Przebieg | Format | Czas [s] | Koszt [$] | Pola | needs_review | Walidacja | Adresat | Uwagi |
|---|---|---|---|---|---|---|---|---|---|
| 1-numer-porzadkowy | r3 | docx | 13.8 | 0.0028 | 54 | 0 | OK | Wójt Gminy Elbląg |  |
| 2-zwrot-oplaty-skarbowej | r3 | docx | 35.5 | 0.01254 | 57 | 3 | OK | Urząd Gminy Stawiguda |  |
| 3-zaswiadczenie | r1 | docx | 16.1 | 0.00368 | 38 | 1 | OK | Urząd Miasta i Gminy Młynary |  |
| 4-swietlica | r3 | docx | 17.4 | 0.00209 | 44 | 1 | OK | Wójt Gminy Płoskinia |  |
| 5-nadplata-podatku | r3 | docx | 26.5 | 0.00469 | 58 | 4 | OK | Urząd Gminy Ulan-Majorat | propozycje: RODZAJE_PODATKOW_LOKALNYCH |
| 6-pas-drogowy | r3 | docx | 72.2 | 0.01419 | 85 | 4 | OK | Urząd Miasta i Gminy Miasteczko |  |
| 7-psy-agresywne | r2 | doc | 16.4 | 0.00395 | 53 | 6 | OK | Urząd Miejski Wrocławia Wydział Środowiska | propozycje: RASY_PSOW_AGRESYWNYCH |
| 8-deklaracja-odpady | r1 | docx | 33.0 | 0.06701 | 93 | 6 | OK | Prezydent Miasta Gdyni |  |
| 9-stypendium-sportowe | r1 | docx | 36.7 | 0.06736 | 100 | 12 | OK | Prezydent Miasta Zgierza | propozycje: DYSCYPLINY_SPORTOWE |
| 7-psy-agresywne-skan | r1 | jpg | 67.3 | 0.01617 | 54 | 4 | OK | Urząd Miejski Wrocławia, Wydział Środowiska | propozycje: RASY_PSOW_AGRESYWNYCH |
| 9-stypendium-sportowe-skan | r2 | png | 98.6 | 0.07155 | 99 | 13 | OK | Prezydent Miasta Zgierza | propozycje: DYSCYPLINY_SPORTOWE, SPOSOBY_DORECZENIA |

Koszt Eden: przebiegi mediany $0.2660, wszystkie 3 przebiegi (33 wywołania) $0.8071, średnio $0.269 za komplet 11 plików.
