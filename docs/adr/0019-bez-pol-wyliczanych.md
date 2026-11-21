# 0019. Bez pól wyliczanych
Data: 2026-11-21 · Status: przyjęta
Źródło: MENTORZY + ZESPÓŁ

## Kontekst
- Formularz #8 (część E) i #6 wymagają obliczeń: `liczba × stawka = opłata`, `SUMA poz. 38, 41, 44 i 47 pomniejszona o 50`, `razem m²`.
- Mentorzy (2026-11-21): JSONata w `states` zwraca **tylko true/false**.
- Schemat też nie ma wyliczania: `states.type` to SHOW lub READ_ONLY, a `defaultValueType` zna tylko EXTERNAL_SYSTEM ([flow-review](../../../research/2026-11-21-flow-review.md), P2).

## Decyzja
- Nie generujemy pól wyliczanych.
- Użytkownik wpisuje dane wejściowe i wynik (pole NUMBER). Stawki i wzór podajemy w `description` pola (ten fragment to nasz wybór, nie odpowiedź mentorów).

## Konsekwencje
- Gorszy UX dla #8 E: wynik wpisuje człowiek, bez kontroli arytmetyki.
- Generator nie musi budować wyrażeń arytmetycznych, a walidator nie sprawdza ich spójności.
- Jeśli Generator COI doda obliczenia, trzeba będzie napisać nowy ADR zastępujący ten.
