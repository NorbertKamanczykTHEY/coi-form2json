# 0002. Python 3.14, uv i licencje bez copyleftu
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (T1, T2) + ZESPÓŁ

## Kontekst
- Wymóg T1: Python 3.14+ jest preferowany. Wymóg T2: tylko open source bez copyleftu (AGPL, GPL), bez licencji komercyjnych, najnowsze stabilne wersje.
- Nasz wybór: menedżer zależności `uv` oraz lista wykluczeń z research (`HANDOFF.md`): PyMuPDF i Ghostscript (AGPL), antiword (GPL). LibreOffice (MPL) uznaliśmy za szarą strefę.
- PoC-1 ([RESULTS](../../../poc-1-ocr/RESULTS.md)): `paddlepaddle` nie ma wheeli dla 3.14, a instalacja `torch` pod Doclingiem zawiesiła się. Kreuzberg (MIT) i Tika działają na 3.14.

## Decyzja
- Backend na Pythonie 3.14, zależności zarządzane przez `uv` (`pyproject.toml` + `uv.lock`, wersje przypięte).
- Każda nowa zależność przechodzi sprawdzenie licencji przed dodaniem. Wykluczone: PyMuPDF, Ghostscript i wszystko na GPL/AGPL.

## Konsekwencje
- PaddleOCR odpada także z powodu braku pakietów dla 3.14 (zob. [0007](0007-t0-lokalnie-skany-do-vlm.md)).
- Konwersja formatów biurowych nie może korzystać z LibreOffice w ścieżce produkcyjnej bez osobnej decyzji. Kreuzberg czyta `.doc` natywnie.
- Sprawdzanie licencji jest ręczne. W dokumentach nie ma automatycznego skanu licencji zależności tranzytywnych.
