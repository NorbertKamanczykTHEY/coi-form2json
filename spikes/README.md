# spikes/ – eksperymenty, z których powstał kod w `backend/coi/`

Kod jednorazowy: prototypy i pomiary sprzed implementacji. **Aplikacja z niego nie korzysta**; zostaje jako dowód decyzji (ADR-y w `docs/adr/`, projekty w `docs/design/`). Wyniki przebiegów (`*/out/`, `e2e-out/`) są w `.gitignore`.

| Katalog | Co sprawdzał | Wynik / gdzie trafiło |
|---|---|---|
| `field-extraction/` | Tekst z parsera → drzewo pól (FieldTree) przez LLM na Eden: prompt, schemat, postprocess, bramka jakości; porównanie modeli (mistral, gemma, qwen) na #1, #3, #5, #7, #9 | Wybrana drabina mistral-small → large i ekstrakcja dwuetapowa dla długich dokumentów → `coi/extraction/`, prompty w `coi/prompts/`. Opis: [docs/design/field-extraction.md](../docs/design/field-extraction.md) |
| `generator/` | Drzewo pól → JSON COI deterministycznie: szablony stron „Dane”, „Kontakt i zgody”, koniec jako dane (`templates/`), layout x/y, UUID, JSONata; `validate.py` (schemat + reguły 1–6), `compare.py` (porównanie z wzorcami #1/#5) | Odtworzone 24/24 wyrażenia JSONata z #1 → `coi/generator/`. Opis: [docs/design/generator.md](../docs/design/generator.md) |
| `dictionary-matching/` | Decyzja „istniejący słownik / nowy / bez słownika” dla pola: porównanie metod (rapidfuzz, modele klasyfikacyjne, LLM) na polach z formularzy #1–#9 | → `coi/dictionaries/` (matcher), ADR 0012. Opis: [docs/dictionaries.md](../docs/dictionaries.md) |
| `e2e-out/` | Lokalne wyniki przebiegów E2E i EVAL (JSON-y, raporty, bazy SQLite) | Tylko lokalnie, poza gitem. Wyniki do oddania: [results/](../results/) |

Wcześniejszy PoC OCR (porównanie Kreuzberg, Tika, Docling, PaddleOCR, Tesseract, VLM) był poza tym repozytorium; jego wnioski są w ADR 0005–0008 i w [docs/design/parser-contract.md](../docs/design/parser-contract.md).
