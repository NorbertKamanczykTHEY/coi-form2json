# 0018. Pola domyślnie wymagane
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (M4) + MENTORZY

## Kontekst
- Reguły techniczne (M4): każde pole ma określoną obligatoryjność. Mentorzy potwierdzili 2026-11-21: **domyślnie required**.
- Wzorce #1 i #5 mają `validation: []` we wszystkich polach, czyli stoją w sprzeczności z regułą ([flow-review](../../../research/2026-11-21-flow-review.md), U2, P5).
- Gwiazdka na papierze nigdy nie oznacza „wymagane”: to „niepotrzebne skreślić” albo przypis (U1).

## Decyzja
- Pole dostaje `validation: ["REQUIRED", …]`, chyba że jest opcjonalne.
- Opcjonalne tylko przy wyraźnym znaczniku („opcjonalnie”, „nieobowiązkowe”, `**`, „ewentualne”, „uwagi”; dane kontaktowe zawsze) albo przy załączniku „można dołączyć”. „Należy dołączyć” jest wymagane.
- Pole warunkowe jest wymagane i ma SHOW. Zostaje niejasne → wymagane i flaga `low_confidence`.
- Pełny zestaw reguł R1–R7 jest w flow-review (pkt 6).

## Konsekwencje
- Świadome odejście od wzorców (puste `validation`). Opisujemy je w README.
- Dla kilku pól na formularz decyzja jest niepewna (R7). Trafiają do `needs_review`.
- Wymaganie na polu ukrytym przez SHOW sprawdza się tylko, gdy pole jest widoczne. To pytanie M2 do mentorów, bez odpowiedzi w dokumentach.
