# 0006. Wykrywanie typu pliku: rozszerzenie i MIME z magic bytes
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (T5) + ZESPÓŁ

## Kontekst
- Wymóg T5: tylko obsługiwane formaty, a MIME musi się zgadzać z rozszerzeniem. Wielkość liter rozszerzenia nie ma znaczenia (`.PDF`, `.DOC` w materiałach).
- To, co znaczy „zgadza się”, jest naszą wykładnią. W materiałach jest `.doc` z zawartością docx oraz plik `.JPE` (#7), który jest poza listą formatów.
- Skany trzeba odróżnić od PDF z warstwą tekstu, bo idą różnymi ścieżkami.

## Decyzja
`detect(data, filename) -> Kind` w czterech krokach:
1. Rozszerzenie z listy dozwolonych, bez względu na wielkość liter. Inaczej 415.
2. Typ z magic bytes (biblioteka `filetype`, MIT).
3. Zgodność z kategorią zadania: DOC = `.doc` albo `.docx`. `.DOC` z docx w środku przyjmujemy jako docx. `.JPE` odrzucamy (415).
4. PDF: warstwa tekstu → `pdf_text`, w przeciwnym razie `pdf_scan` (decyzja per strona, orientacyjnie < ~50 znaków na stronę).

## Konsekwencje
- Niezgodność poza kategorią daje 415. Za duży plik daje 413, a nazwę niezgodną z T6 odrzuca API kodem 400.
- Próg „warstwa tekstu” jest orientacyjny. Ustala go implementujący na plikach z materiałów i na skanie zrobionym z #1.
- Przyjęcie `.DOC` z docx to nasza interpretacja T5. Jeśli jury rozumie wymóg dosłownie, ten plik powinien dostać 415.
