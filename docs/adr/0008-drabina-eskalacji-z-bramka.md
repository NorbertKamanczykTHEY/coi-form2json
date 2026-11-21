# 0008. Drabina eskalacji z bramką jakości
Data: 2026-11-21 · Status: przyjęta
Źródło: ZESPÓŁ

## Kontekst
- Finaliści uruchamiają rozwiązanie na nowych plikach (pkt 6 zadania), więc potrzebny jest odporny przebieg na formularzach, których nie widzieliśmy. Samo zadanie nie określa mechanizmu.
- Projekt: [gate-design](../../../poc-1-ocr/research/gate-design.md). Zasada: każdy krok kończy się tanim, deterministycznym sprawdzeniem, a model nie jest jedynym sędzią własnej pracy.

## Decyzja
- Drabina per strona lub kafel, nie per plik: L0 Kreuzberg → L1 mały VLM (≈8B) + świadek Tesseract → L2 duży VLM innej rodziny tylko na spornych kaflach → L3 wynik z `confidence` i `needs_review`.
- Bramka po Kreuzbergu: śmieci, polszczyzna, forma formularza, spójność struktury. Bramka po modelu: schemat, brak halucynacji, brak pominięć, geometria, sygnały flow.
- Szczeble modeli są w `ladder.json` (`LADDER_PATH`), więc podmiana modelu to zmiana konfiguracji.
- „Nie zawodzimy po cichu”: odpowiedź niesie `trace[]` (poziom, sygnały, decyzja) i flagi `needs_review` per pole i strona (`?report=true`).

## Konsekwencje
- Progi bramki (np. 3% śmieci, fuzzy ≥ 85, pokrycie ≥ 90%) są wstępne. Plan kalibracji na #1–#9 i wariantach zepsutych jest w gate-design (pkt 4), dane są na razie tylko dla #1 i #7.
- L2 kosztuje ×5–10 na stronę, więc koszt na formularz zależy od odsetka eskalacji (kryterium „potencjał wdrożeniowy”).
- Urzędnik poprawia pola `needs_review` we froncie (R-IV).
