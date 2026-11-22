# Parsowanie plików: mapa typ → parser i kontrakt `ParsedDocument`

Przeniesione ze specyfikacji z 2026-11-21 (`docs/superpowers/specs/2026-11-21-parser-contract-design.md`, poza repozytorium) i zaktualizowane do kodu z 2026-11-22. Decyzje: [ADR 0005](../adr/0005-mapa-parserow-i-parseddocument.md), [0006](../adr/0006-wykrywanie-typu-pliku.md), [0007](../adr/0007-t0-lokalnie-skany-do-vlm.md), [0008](../adr/0008-drabina-eskalacji-z-bramka.md), [0009](../adr/0009-parsowanie-konczy-sie-na-parseddocument.md). Kod: `backend/coi/parsing/`.

## Cel
Pierwszy krok pipeline'u zamienia plik na jedną strukturę niezależną od narzędzia (`ParsedDocument`). Kolejne kroki (ekstrakcja pól, generator) nie wiedzą, który parser zadziałał. Wymiana parsera albo modelu to zmiana konfiguracji (`ladder.json`), bez zmian w kolejnych krokach.

- **Cele:** wszystkie formaty z zadania, jeden kontrakt, jedno publiczne API.
- **Nie-cele:** strumieniowanie, pamięć podręczna wyników, wtyczki przez entry points.
- **Anty-cele:** kolejne kroki zależne od konkretnego parsera (np. szukanie `❑` albo `U` w tekście), usługa OCR wystawiona na zewnątrz.

## Rozpoznanie typu pliku (`detect.py`)
```
detect(data: bytes, filename: str) -> Kind
  1. rozszerzenie z listy dozwolonych (bez rozróżniania wielkości liter), inaczej 415
  2. typ z magic bytes (biblioteka filetype, MIT)
  3. zgodność z kategorią zadania: DOC = .doc|.docx (dlatego .DOC z docx w środku przechodzi), inaczej 415
  4. pdf: warstwa tekstu oceniana dla każdej strony osobno (pdf_min_chars w ladder.json)
Kind ∈ {docx, doc, ods, xlsx, pdf_text, pdf_scan, image}
```
Rozmiar ponad `MAX_FILE_MB` daje 413 (`TooLarge`).

## Mapa parserów
| Wejście | Ścieżka |
|---|---|
| docx, doc, ods, xlsx | Kreuzberg (tekst w procesie). Bramka G1/G2, G3 dla całego dokumentu. Przy porażce tylko ostrzeżenie: bez LibreOffice nie ma obrazu strony |
| pdf | każda strona osobno: z warstwą tekstu → Kreuzberg; bez tekstu albo ze śmieciami → render strony i ścieżka skanu |
| jpg, jpeg, png, strony skanu pdf | T0: Tesseract `pol` (CLI). Gdy bramka odrzuci wynik, kolejne szczeble VLM z `ladder.json` (Eden) albo `ladder.local.json` (air gap). Wynik VLM jest sprawdzany względem Tesseracta jako świadka (kompletność, pokrycie słów, nagłówki wersalikami) |

Zmiana względem specyfikacji z 2026-11-21: zamiast kontenera PaddleOCR (brak wheeli dla Pythona 3.14, 100–120 s na CPU) T0 to Tesseract w obrazie backendu, a trudne strony idą do modelu wizyjnego ([ADR 0007](../adr/0007-t0-lokalnie-skany-do-vlm.md)). Nie ma żadnego kontenera pomocniczego.

## Interfejs
```python
parse(data: bytes, filename: str, cfg: Config | None = None, on_event=None) -> ParsedDocument
```
Wyjątki: `TooLarge` (413), `UnsupportedType` (415), `ParserEnvironmentError` (500: brak Tesseracta albo klucza LLM), `ParsingError` Kreuzberga (422: zepsuty plik). `on_event(event, payload)` dostaje `escalation` po każdej próbie VLM i `warning` na końcu.

## Kontrakt `ParsedDocument` (`model.py`)
```
source:   {filename, kind, mime, parser, parser_version, seconds, cost}
pages:    [{number, blocks: [Block]}]           # kolejność czytania
warnings: [str]                                 # każde obejście
trace:    [{page, step, parser, model, gate, seconds, cost, error, …}]   # każda decyzja drabiny

Block:
  kind:       heading | paragraph | list_item | table | footnote
  text:       str            # znaczniki znormalizowane (niżej)
  level:      int | None     # heading: 1 = „A.”, „1.”, „I.”; 2 = „B.1”, „2.1”
  rows:       [[str]] | None # table; scalone komórki zdeduplikowane
  bbox:       [x0,y0,x1,y1] | None  # tylko OCR/VLM
  confidence: float | None          # tylko OCR
```
Zwykłe dataclassy z `to_dict()`. Ten sam słownik trafia do `editor.source` w odpowiedzi API.

## Normalizacja znaczników (`normalize.py`)
| Na wejściu | Na wyjściu |
|---|---|
| `❑ □ ☐ ▢`, w Tesseract `U`, `Q` na początku pozycji wyboru | `☐` |
| kropki, `…`, podkreślenia (≥ 4 znaki) | `___` |
| `*`, `**`, `1)`, przypisy | bez zmian |

`to_markdown(doc)` (`markdown.py`) przygotowuje wejście dla modelu, a ekstrakcja dokłada kotwice `[p<strona>.b<blok>]` (`extraction/anchors.py`).

## Testy
- `tests/parsing/test_contract.py`: jeden zestaw kontraktu na wszystkich formatach (struktura, znaczniki `☐` i `___`, frazy kontrolne).
- `tests/parsing/test_detect.py`: rozszerzenia, magic bytes, 415.
- `tests/parsing/test_airgap.py`: przy `LLM_PROVIDER=local` jedyny rozwiązywany host to `127.0.0.1`.
- `-m eden`: przebieg z prawdziwym Edenem (około 1 centa), domyślnie wyłączony.
