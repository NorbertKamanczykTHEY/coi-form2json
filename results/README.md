# Wyniki E2E (docker compose, POST /api/v1/forms?report=true)

Kod: obraz z commita 73f1ee7 (przed poprawkami po EVAL, fcc4dae). Skrypt: `run.py`. Walidacja: `POST /forms/validate` i schemat z `materials/`.

| Plik | Format | Czas [s] | Koszt [$] | Pola | needs_review | Walidacja | Uwagi |
|---|---|---|---|---|---|---|---|
| 1-numer-porzadkowy | docx | 24.3 | 0.01046 | 54 | 4 | OK |  |
| 2-zwrot-oplaty-skarbowej | docx | 864.7 | 0.02069 | 67 | 2 | OK |  |
| 3-zaswiadczenie | docx | 8.8 | 0.00105 | 60 | 7 | OK |  |
| 4-swietlica | docx | 48.5 | 0.00947 | 43 | 3 | OK |  |
| 5-nadplata-podatku | docx | 10.4 | 0.00158 | 56 | 3 | OK | propozycje: RODZAJE_PODATKOW_LOKALNYCH |
| 6-pas-drogowy | docx | 25.2 | 0.00414 | 77 | 3 | OK |  |
| 7-psy-agresywne | doc | 31.4 | 0.00503 | 47 | 7 | OK | propozycje: RASY_PSOW_AGRESYWNYCH |
| 8-deklaracja-odpady | docx | 65.0 | 0.01451 | 67 | 9 | OK |  |
| 9-stypendium-sportowe | docx | 147.9 | 0.04781 | 143 | 23 | OK | propozycje: DYSCYPLINY_SPORTOWE |
| 7-psy-agresywne-skan | jpg | 63.9 | 0.00933 | 60 | 10 | OK | propozycje: RASY_PSOW_AGRESYWNYCH |
| 9-stypendium-sportowe-skan | png | 167.4 | 0.05403 | 126 | 155 | OK | propozycje: DYSCYPLINY_SPORTOWE |

Łączny koszt Eden tego przebiegu: $0.1781.
