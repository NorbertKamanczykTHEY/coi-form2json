# 0014. Postęp przez SSE w tym samym żądaniu, bez kolejki zadań
Data: 2026-11-21 · Status: przyjęta
Źródło: ZESPÓŁ

## Kontekst
- Ekstrakcja bywa długa (VLM: 34–43 s na obraz online, [RESULTS](../../../poc-1-ocr/RESULTS.md)). Front ma pokazać kroki (T0 → VLM, bramka), co podnosi intuicyjność (kryterium oceny).
- Zadanie nie wymaga postępu. Wymaga za to, by plik istniał tylko na czas żądania (T8), a kolejka zadań oznaczałaby trzymanie go dłużej.
- Kolejka zadań jest w [api-assumptions](../api-assumptions.md) poza zakresem.

## Decyzja
- To samo żądanie `POST /api/v1/forms` z `Accept: text/event-stream` zwraca strumień zdarzeń `stage`, `escalation`, `warning`, a na końcu `result`.
- Bez `Accept: text/event-stream` zachowuje się synchronicznie ([0013](0013-post-forms-synchronicznie.md)).
- Brak kolejki, workerów i przechowywania pliku po zakończeniu żądania.

## Konsekwencje
- Połączenie jest otwarte przez całą ekstrakcję. Nginx w froncie musi przekazywać strumień bez buforowania, a klient musi znieść zerwanie połączenia.
- Zerwanie połączenia nie wznawia pracy: wynik trzeba zażądać ponownie. Wynik zapisany w bazie można odczytać przez `GET /forms/{id}`.
- Wątki strumienia nie dzielą połączenia z bazą, bo `Store` otwiera krótkie połączenie na wywołanie ([storage](../storage.md)).
