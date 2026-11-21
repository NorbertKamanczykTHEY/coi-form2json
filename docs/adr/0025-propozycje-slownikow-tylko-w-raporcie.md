# 0025. Propozycje słowników tylko w raporcie i w edytorze, JSON COI ma wyłącznie słowniki istniejące
Data: 2026-11-21 · Status: przyjęta
Źródło: UŻYTKOWNIK

## Kontekst
- `match()` zwraca słownik istniejący (`decision: "existing"`) albo propozycję nowego (`"new"`, z naszego katalogu albo z opcji w dokumencie).
- Generator wpisywał też propozycje do pola. JSON COI wskazywał wtedy słownik, którego w COI jeszcze nie ma, np. „Rasa psa” w #7 dostawała `RASY_PSOW_AGRESYWNYCH`, więc formularz nie dał się zaimportować bez wcześniejszego założenia słownika.

## Decyzja
- Domyślnie (`POST /api/v1/forms` bez parametrów) JSON COI zawiera tylko słowniki istniejące. Pole z propozycją zostaje takie jak bez słownika: TEXT_FIELD albo pole z własnymi `options`.
- Propozycje trafiają do `report.proposed_dictionaries` z listą pól, których dotyczą.
- Z `?editor=true` edytor dostaje `editor.proposals[]` = `{dictionary, fieldIds, changes}`. Akceptacja to `POST /api/v1/dictionaries/from-proposal` (słownik trafia do bazy, a słownik z katalogu staje się słownikiem użytkownika), a potem `PUT /api/v1/forms/{id}` z polem przestawionym według `changes`.
- RADIO zawsze ma opcje w polu. Propozycja z treści dokumentu powstaje tylko dla SELECT.

## Konsekwencje
- Wynik domyślny zawsze da się zaimportować do COI bez zakładania słowników.
- Słownik zaakceptowany raz jest dla kolejnych formularzy słownikiem istniejącym i trafia do pola od razu.
- `POST /api/v1/dictionaries` nie służy do akceptacji: dla słownika z katalogu zwraca 409, bo jego id już jest w bazie, i wymaga płaskiej listy pozycji z `id`. Robi to `from-proposal`.
