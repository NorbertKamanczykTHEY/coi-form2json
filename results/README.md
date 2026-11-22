# Wyniki E2E (docker compose, POST /api/v1/forms?report=true)

Kod: obraz z HEAD af98b50 (generator i ekstrakcja po EVAL-3). Każdy plik przeszedł 3 razy; tu leży **przebieg mediany** (kolumna „Przebieg”, mediana liczby pól, przy remisie needs_review, potem niższy koszt). Zmienność 3 przebiegów: [eval-4/zmiennosc.md](eval-4/zmiennosc.md), ocena ekspercka: [eval-4/README.md](eval-4/README.md).

Skrypt: `run.py` (z app/backend: `PYTHONPATH=. uv run python ../results/run.py`). Walidacja: `POST /forms/validate` i schemat z `materials/`. Czasy pochodzą z 3 przebiegów puszczonych równolegle na tym samym kontenerze, więc są zawyżone względem pojedynczego przebiegu.

| Plik | Przebieg | Format | Czas [s] | Koszt [$] | Pola | needs_review | Walidacja | Adresat | Uwagi |
|---|---|---|---|---|---|---|---|---|---|
| 1-numer-porzadkowy | r2 | docx | 8.3 | 0.00116 | 54 | 0 | OK | Wójt Gminy Elbląg |  |
| 2-zwrot-oplaty-skarbowej | r2 | docx | 47.1 | 0.01198 | 57 | 0 | OK | Urząd Gminy Stawiguda |  |
| 3-zaswiadczenie | r2 | docx | 4.8 | 0.00052 | 39 | 0 | OK | Urząd Miasta i Gminy Młynary |  |
| 4-swietlica | r3 | docx | 36.9 | 0.00825 | 42 | 6 | OK | Wójt Gminy Płoskinia |  |
| 5-nadplata-podatku | r1 | docx | 32.1 | 0.00753 | 58 | 2 | OK | Urząd Gminy Ulan-Majorat | propozycje: RODZAJE_PODATKOW_LOKALNYCH |
| 6-pas-drogowy | r1 | docx | 82.1 | 0.01916 | 85 | 11 | OK | Urząd Miasta i Gminy Miasteczko |  |
| 7-psy-agresywne | r3 | doc | 45.1 | 0.00949 | 52 | 5 | OK | Urząd Miejski Wrocławia, Wydział Środowiska | propozycje: RASY_PSOW_AGRESYWNYCH |
| 8-deklaracja-odpady | r2 | docx | 215.4 | 0.0752 | 113 | 25 | OK | Prezydent Miasta Gdyni |  |
| 9-stypendium-sportowe | r2 | docx | 178.1 | 0.06097 | 76 | 18 | OK | Prezydent Miasta Zgierza | propozycje: DYSCYPLINY_SPORTOWE |
| 7-psy-agresywne-skan | r2 | jpg | 62.2 | 0.01037 | 49 | 6 | OK | Urząd Miejski Wrocławia Wydział Środowiska | propozycje: RASY_PSOW_AGRESYWNYCH |
| 9-stypendium-sportowe-skan | r1 | png | 224.1 | 0.0678 | 75 | 20 | OK | Prezydent Miasta Zgierza | propozycje: DYSCYPLINY_SPORTOWE |

Koszt Eden: przebiegi mediany $0.2724, wszystkie 3 przebiegi (33 wywołania) $0.7786.
