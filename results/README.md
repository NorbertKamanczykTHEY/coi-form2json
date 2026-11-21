# Wyniki E2E (docker compose, POST /api/v1/forms?report=true)

Kod: obraz z HEAD e2a4acd (generator po poprawkach z EVAL, fcc4dae). Skrypt: `run.py` (z app/backend: `uv run python ../results/run.py`). Walidacja: `POST /forms/validate` i schemat z `materials/`.

| Plik | Format | Czas [s] | Koszt [$] | Pola | needs_review | Walidacja | Adresat | Uwagi |
|---|---|---|---|---|---|---|---|---|
| 1-numer-porzadkowy | docx | 3.6 | 0.0004 | 52 | 0 | OK | Wójt Gminy Elbląg |  |
| 2-zwrot-oplaty-skarbowej | docx | 5.2 | 0.00076 | 53 | 2 | OK | Urząd Gminy Stawiguda |  |
| 3-zaswiadczenie | docx | 3.8 | 0.0005 | 36 | 1 | OK | Urząd Miasta i Gminy Młynary |  |
| 4-swietlica | docx | 4.7 | 0.00063 | 38 | 1 | OK | Wójt Gminy Płoskinia |  |
| 5-nadplata-podatku | docx | 9.9 | 0.00133 | 56 | 2 | OK | Urząd Gminy Ulan-Majorat | propozycje: RODZAJE_PODATKOW_LOKALNYCH |
| 6-pas-drogowy | docx | 26.1 | 0.00359 | 68 | 1 | OK | Burmistrz Miasta i Gminy w Daleszycach |  |
| 7-psy-agresywne | doc | 39.3 | 0.00657 | 52 | 5 | OK | Urząd Miejski Wrocławia, Wydział Środowiska | propozycje: RASY_PSOW_AGRESYWNYCH |
| 8-deklaracja-odpady | docx | 275.0 | 0.07494 | 115 | 0 | OK | Prezydent Miasta Gdyni |  |
| 9-stypendium-sportowe | docx | 177.9 | 0.05991 | 124 | 4 | OK | Prezydent Miasta Zgierza | propozycje: DYSCYPLINY_SPORTOWE |
| 7-psy-agresywne-skan | jpg | 53.3 | 0.00878 | 54 | 6 | OK | Wydział Środowiska Urzędu Miejskiego Wrocławia | propozycje: RASY_PSOW_AGRESYWNYCH |
| 9-stypendium-sportowe-skan | png | 187.3 | 0.05899 | 106 | 5 | OK | Prezydent Miasta Zgierza | propozycje: DYSCYPLINY_SPORTOWE |

Łączny koszt Eden tego przebiegu: $0.2164.
