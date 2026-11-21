# 0007. T0 lokalnie (Kreuzberg + Tesseract), skany i obrazy do VLM
Data: 2026-11-21 · Status: przyjęta
Źródło: ZESPÓŁ

## Kontekst
Wymogi T2 i T3 zawężają wybór (bez copyleftu, bez modeli tylko przez API). Wybór narzędzi wynika z pomiarów w [PoC-1](../../../poc-1-ocr/RESULTS.md) (formularz #1, 8 formatów):
- **Pliki z tekstem:** Kreuzberg ma 100% pól, 2–240 ms na plik, MIT, działa na 3.14, czyta `.doc` bez Javy i LibreOffice.
- **Obrazy:** Qwen3-VL-8B jako jedyny zachowuje miejsca na wpis (`leaders` 9) i daje `anchor_exact` 1.0, ale 34–43 s online. Tesseract przez Kreuzberga: 1,2–1,4 s, gubi kropki i pojedyncze pola.
- PaddleOCR: najlepszy klasyczny OCR, lecz 100–120 s na CPU i brak wheeli dla 3.14.

## Decyzja
- T0 lokalnie: Kreuzberg z Tesseract `pol` dla formatów dokumentowych (PDF, DOC/DOCX, ODS, XLSX). Tesseract jest też szybkim trybem awaryjnym i świadkiem bramki ([0008](0008-drabina-eskalacji-z-bramka.md)).
- Skany i obrazy (JPG, JPEG, PNG, strony PDF bez tekstu) idą do VLM.
- PaddleOCR, Docling i Tika nie wchodzą do runtime.

## Konsekwencje
- Jakość skanów zależy od dostępności VLM (Eden albo lokalny, zob. [0010](0010-adapter-dostawcy-modeli-i-air-gap.md)).
- Czas lokalnego Qwen3-VL-8B (ollama, M4 i CPU) nie jest zmierzony. RESULTS wymienia to jako „do sprawdzenia przed decyzją”.
- PoC był na czystym renderze #1, nie na prawdziwym skanie. Wynik dla skanów jest niepotwierdzony.
