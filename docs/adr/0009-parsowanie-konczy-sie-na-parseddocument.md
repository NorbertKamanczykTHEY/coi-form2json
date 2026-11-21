# 0009. Serwis parsowania kończy się na `ParsedDocument`
Data: 2026-11-21 · Status: przyjęta
Źródło: ZESPÓŁ

## Kontekst
- Pipeline ma cztery stopnie: parsowanie, ekstrakcja pól (drzewo `FieldTree`, `app/spikes/field-extraction/`), generator deterministyczny ([generator](../design/generator.md)) i walidator.
- Ekstrakcja używa LLM i jest rozwijana osobno. Generator jest deterministyczny i nie używa LLM.
- Specyfikacja parsera stawia anty-cel: kolejne kroki zależne od konkretnego parsera (szukanie `❑` albo `U` w tekście).

## Decyzja
- Moduł parsowania zwraca wyłącznie `ParsedDocument` ([0005](0005-mapa-parserow-i-parseddocument.md)) i nie wie nic o polach formularza.
- Ekstrakcja pól to osobny krok, który dostaje `ParsedDocument` (przez `to_markdown(doc)` albo bloki) i zwraca `FieldTree`.

## Konsekwencje
- Granica modułów jest też granicą testów. Parsery testujemy kontraktem, ekstrakcję na `FieldTree`, generator na wzorcach #1 i #5.
- `bbox` i `confidence` z `ParsedDocument` zasilają `field_map` dla edytora (`?editor=true`).
- Zmiana kształtu `ParsedDocument` dotyka wszystkich adapterów i ekstrakcji, więc wymaga nowego ADR.
