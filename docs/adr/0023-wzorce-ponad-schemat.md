# 0023. Przy rozbieżności schematu i wzorców trzymamy się wzorców #1 i #5
Data: 2026-11-21 · Status: proponowana
Źródło: SPEC (M3) + ZESPÓŁ

## Kontekst
- M3: JSON ma być zgodny ze strukturą oczekiwaną: schematem i wzorcami #1, #5. Obie wersje się rozchodzą:
  - schemat `repetingSectionGrid` (literówka), wzorce `repeatingSectionGrid`;
  - `validation: {}` w trzech polach #1, `[]` gdzie indziej;
  - `multiLevelTree`, `searchEnabled`, `minItemRows` są we wzorcach, nie w schemacie;
  - `defaultValue` SELECT to w schemacie string, we wzorcach tablica.
- Pełna lista: [generator](../design/generator.md), „Rozbieżności w materiałach”.

## Decyzja
- Emitujemy tak jak wzorce (np. `repeatingSectionGrid`), a `validation` zawsze jako lista.
- Walidator końcowy pomija znany konflikt `defaultValue`. Regresja `compare.py` porównuje strukturę z #1 i #5.

## Konsekwencje
- Zakładamy, że import w Generatorze COI akceptuje to, co dają wzorce. Nie sprawdziliśmy tego na prawdziwym imporcie. Do potwierdzenia u mentorów ([HANDOFF](../../../HANDOFF.md)).
- Walidacja wobec samego schematu przepuszcza więcej, niż wymagałby ścisły import, bo schemat prawie nic nie sprawdza.
- Zmiana wzorców przez organizatora wymaga przeglądu szablonów w `templates/`.
