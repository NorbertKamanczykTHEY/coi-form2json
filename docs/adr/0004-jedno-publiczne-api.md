# 0004. Jedno publiczne API, usługi pomocnicze w sieci wewnętrznej
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (T4, T10) + ZESPÓŁ

## Kontekst
- Wymóg T4: REST API przyjmuje jeden plik. Wymóg T10: tylko potrzebne porty.
- Specyfikacja parsera rozważała trzy podejścia: parser w procesie z mapą w konfiguracji (A), każdy parser jako usługa HTTP (B), wtyczki przez entry points (C). Wybrano A. B odrzucono, bo daje więcej kontenerów i sieci, a Kreuzberg działa w procesie w milisekundach.
- Anty-cel specyfikacji: wystawienie usługi OCR na zewnątrz.

## Decyzja
- Na zewnątrz działa jedno API (`/api/v1`) backendu. Front w produkcji wchodzi przez nginx tym samym originem (`/api` → backend), CORS jest wyłączony.
- Usługi pomocnicze (ewentualny kontener Kreuzberg, serwer modeli) działają w sieci wewnętrznej compose i nie publikują portów.

## Konsekwencje
- Opublikowane są tylko porty backendu i frontu. Usług pomocniczych nie da się wywołać z hosta bez zmiany compose.
- Adapter parsera, który woła kontener pomocniczy, zachowuje ten sam kontrakt JSON (zob. [0005](0005-mapa-parserow-i-parseddocument.md)).
- Mniejsza powierzchnia ataku i mniej konfiguracji CORS kosztem trudniejszego debugowania usług wewnętrznych.
