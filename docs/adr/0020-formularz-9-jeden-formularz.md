# 0020. Formularz #9: jeden formularz, radio „rodzaj wniosku” i flow liniowy
Data: 2026-11-21 · Status: przyjęta
Źródło: MENTORZY + SPEC (R-III)

## Kontekst
- #9 łączy trzy wnioski (stypendium, nagroda, wyróżnienie). Mentorzy (2026-11-21): **jeden plik → jeden formularz**.
- Zależności i dynamiczne przepływy to rozszerzenie R-III. Schemat nie ma warunków na przejściach: `flow.links` to `{id, source, target}`, a strony nie mają `states`.

## Decyzja
- Jeden JSON. Na pierwszej stronie przedmiotu radio „Rodzaj wniosku” (I/II/III), a sekcje warunkowe mają SHOW. Wspólne sekcje definiujemy raz.
- Flow liniowy. Zależność między stronami działa, bo JSONata adresuje stronę po tytule ([generator](../design/generator.md), pkt 7).
- Opcję „Prezydent Miasta” w wariancie wnioskodawcy usuwamy. Standard zakłada, że formularz wypełnia obywatel (P3).

## Konsekwencje
- Strona, której wszystkie sekcje są ukryte, wyświetli się pusta. Ekstrakcja dzieli #9 na strony tematyczne wspólne dla wariantów, a generator ostrzega, gdy wszystkie sekcje strony mają SHOW.
- Decyzja o „Prezydent Miasta” jest naszą rekomendacją. Flow-review oznacza P3 jako pytanie do mentorów, bez zapisanej odpowiedzi.
- Warunkowe przejścia między stronami nie są wspierane przez schemat.
