# 0012. Decyzja „istniejący / nowy / bez słownika”: model klasyfikacyjny
Data: 2026-11-21 · Status: proponowana
Źródło: SPEC (R-I, R-II) + ZESPÓŁ

## Kontekst
- Zadanie wymaga powiązania pól ze słownikami (R-I) i propozycji nowego słownika (R-II). Nie mówi, jak podjąć decyzję dla pola.
- Wcześniejszy projekt ([flow-review](../flow-scenarios.md), pkt 4): katalog znanych słowników z aliasami i fuzzy, a przy braku dopasowania LLM-sędzia zwracający `{K1, K2, K3}`. [Generator](../design/generator.md) woła `match(label, source_label, type, options) -> DictMatch | None`.
- Wątek słowników nadal wybiera mechanizm.

## Decyzja
- Rozstrzyga model klasyfikacyjny z otwartymi wagami, o ile taki istnieje i pasuje do zadania.
- W przeciwnym razie: LLM (jak w projekcie z flow-review) albo samo dopasowanie `rapidfuzz` do katalogu.
- Interfejs `match(...)` zostaje stały, więc wybór nie zmienia generatora.

## Konsekwencje
- Dokumenty nie wskazują konkretnego modelu klasyfikacyjnego ani nie potwierdzają, że taki istnieje dla polskich etykiet pól.
- Model musi działać także w trybie air gap ([0010](0010-adapter-dostawcy-modeli-i-air-gap.md)), co ogranicza wybór do wag uruchamianych lokalnie.
- Status zmieni się na „przyjęta”, gdy wątek słowników zamknie wybór.
