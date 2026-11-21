# 0005. Mapa typ pliku → parsery i kontrakt `ParsedDocument`
Data: 2026-11-21 · Status: przyjęta
Źródło: ZESPÓŁ

## Kontekst
- Zadanie wymaga formatów PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG (M1), ale nie mówi, jak je czytać. Wybór narzędzi i kontraktu jest nasz.
- Cel ([spec parsera](../../../docs/superpowers/specs/2026-11-21-parser-contract-design.md)): kolejne kroki nie wiedzą, który parser zadziałał. Wymiana parsera to zmiana konfiguracji.
- Błędy rozpoznawania zależą od narzędzia (np. `U` i `Q` zamiast pola wyboru w Tesseract).

## Decyzja
- Mapa `Kind` → lista parserów jest w konfiguracji. Kolejność jest fallbackiem: następny parser startuje po błędzie albo pustym dokumencie, a przejście trafia do `warnings`.
- Wspólny kontrakt `ParsedDocument`: `source`, `pages[] → blocks[]` (`heading`, `paragraph`, `list_item`, `table`, `footnote`), `bbox` i `confidence` tylko dla OCR/VLM.
- Znaczniki normalizuje adapter parsera: `❑ □ ☐ ▢` → `☐`, kropki, `…` i podkreślenia (≥ 4 znaki) → `___`.

## Konsekwencje
- Jeden zestaw testów kontraktu biegnie na każdym parserze z konfiguracji. Nowy parser wchodzi do mapy po jego przejściu.
- Koszt: więcej pracy w każdym adapterze, bo normalizacja i poziomy nagłówków są po jego stronie.
- Mapa w specyfikacji (`pdf_scan`, `image`: `paddle_http`, `kreuzberg_tesseract`) jest nieaktualna po [0007](0007-t0-lokalnie-skany-do-vlm.md).
