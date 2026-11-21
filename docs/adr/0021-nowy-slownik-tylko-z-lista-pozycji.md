# 0021. Nowy słownik tylko wtedy, gdy mamy listę pozycji
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (R-II) + ZESPÓŁ

## Kontekst
- Wymóg R-II (i Słowniki.docx): propozycja nowego słownika z **nazwą, strukturą i zastosowaniem**. Dokumenty nie wymagają listy pozycji i nie zabraniają propozycji bez niej.
- Reguła „bez listy nie tworzymy” jest więc **naszą decyzją**, nie wymogiem ([flow-review](../../../research/2026-11-21-flow-review.md), pkt 4).
- Przykłady: #9 dyscypliny (lista w dokumencie), #7 rasa psa (lista poza dokumentem, w rozporządzeniu).

## Decyzja
- Propozycja powstaje tylko wtedy, gdy lista pozycji jest w dokumencie albo w naszym katalogu przygotowanym offline z tekstów źródłowych.
- Propozycja trafia do `report.proposed_dictionaries` (`name`, poziomy, pozycje, `usedIn`). Użytkownik przyjmuje ją endpointem (`POST /api/v1/dictionaries`), po czym kolejne formularze dopasują ją jako istniejącą.
- Kryterium: dziedzina wartości spoza formularza (K1), użycie w innej e-usłudze (K2), wartości to nazwy bytów (K3).

## Konsekwencje
- Brak halucynowanych pozycji, wynik deterministyczny. Model nigdy nie wymyśla pozycji.
- Bez listy pole zostaje `TEXT_FIELD` albo `options`, np. rasy psów (#7), dopóki katalog nie powstanie. Lista 11 ras wymaga potwierdzenia.
- Jeśli jury oczekuje propozycji bez listy, stracimy punkty w progu II.
