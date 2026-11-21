# Wyniki E2E (docker compose, POST /api/v1/forms?report=true)

Kod: obraz z HEAD c935629 (strony postępowania, `applicant_self_only`, `entity_extract_required`). Skrypt: `run.py` (z app/backend: `PYTHONPATH=. uv run python ../results/run.py`). Walidacja: `POST /forms/validate` i schemat z `materials/`. Ocena ekspercka tego przebiegu: [eval-3/README.md](eval-3/README.md).

| Plik | Format | Czas [s] | Koszt [$] | Pola | needs_review | Walidacja | Adresat | Uwagi |
|---|---|---|---|---|---|---|---|---|
| 1-numer-porzadkowy | docx | 10.1 | 0.00318 | 53 | 0 | OK | Wójt Gminy Elbląg |  |
| 2-zwrot-oplaty-skarbowej | docx | 51.0 | 0.01735 | 66 | 10 | OK | Urząd Gminy Stawiguda |  |
| 3-zaswiadczenie | docx | 4.6 | 0.00137 | 36 | 0 | OK | Urząd Miasta i Gminy Młynary |  |
| 4-swietlica | docx | 45.2 | 0.00946 | 43 | 4 | OK | Wójt Gminy Płoskinia |  |
| 5-nadplata-podatku | docx | 20.2 | 0.00382 | 58 | 2 | OK | Urząd Gminy Ulan-Majorat | propozycje: RODZAJE_PODATKOW_LOKALNYCH |
| 6-pas-drogowy | docx | 69.2 | 0.01453 | 70 | 8 | OK | Urząd Miasta i Gminy Miasteczko |  |
| 7-psy-agresywne | doc | 19.3 | 0.00351 | 41 | 5 | OK | Urząd Miejski Wrocławia Wydział Środowiska | propozycje: RASY_PSOW_AGRESYWNYCH |
| 8-deklaracja-odpady | docx | 184.5 | 0.05729 | 120 | 22 | OK | Prezydent Miasta Gdyni |  |
| 9-stypendium-sportowe | docx | 224.7 | 0.06655 | 151 | 5 | OK | Prezydent Miasta Zgierza | propozycje: DYSCYPLINY_SPORTOWE |
| 7-psy-agresywne-skan | jpg | 60.1 | 0.00974 | 46 | 5 | OK | Urząd Miejski Wrocławia Wydział Środowiska | propozycje: RASY_PSOW_AGRESYWNYCH |
| 9-stypendium-sportowe-skan | png | 171.2 | 0.05994 | 144 | 7 | OK | Prezydent Miasta Zgierza | propozycje: SPOSOBY_DORECZENIA, DYSCYPLINY_SPORTOWE |

Łączny koszt Eden tego przebiegu: $0.2467.
