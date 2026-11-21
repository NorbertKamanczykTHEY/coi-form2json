# 0011. Sekrety tylko w `.env` i zmiennych środowiskowych
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (T10, T11) + ZESPÓŁ

## Kontekst
- Wymóg T10: sekrety podawane w runtime. Wymóg T11: konfiguracja obejmuje JWT i parametry integracji.
- Sekrety w projekcie: klucz Eden (`LLM_API_KEY`, alias `EDENAI_API_KEY`) i `JWT_SECRET`. Repozytorium git jest publiczne w oddaniu (film i kod w otwartym repo).

## Decyzja
- Sekrety są tylko w `app/.env` (poza gitem, w `.gitignore`) albo w zmiennych środowiskowych kontenera. W repo jest `.env.example` bez wartości.
- Nigdy w kodzie, w warstwach obrazu, w commitach ani w logach. Logi nie zawierają treści plików ani kluczy (`LOG_LEVEL`).
- Baza nie przechowuje tokenów JWT ani kluczy LLM ([storage](../storage.md)).
- W trybie air gap klucz Eden nie jest potrzebny ([0010](0010-adapter-dostawcy-modeli-i-air-gap.md)).

## Konsekwencje
- Każdy nowy parametr integracji trafia do `.env.example`.
- Pilnowanie logów jest dyscypliną w kodzie. W dokumentach nie ma automatycznego testu, który wykryłby klucz w logu.
- Wyciek klucza w historii git wymagałby jego unieważnienia, bo repozytorium ma być otwarte.
