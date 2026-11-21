# 0022. Dane inicjalne: konfigurujemy źródło i atrybut, niczego nie wypełniamy
Data: 2026-11-21 · Status: proponowana
Źródło: SPEC (R-I) + ZESPÓŁ

## Kontekst
- R-I: słowniki i dane inicjalne powiązane z pasującymi polami. Dane inicjalne pochodzą z systemów zewnętrznych (źródła PESEL, PESEL_ADDRESS, MLPZ), a pole ma `readOnly: true`, `defaultValue: "MLPZ.surname"`, `defaultValueType: "EXTERNAL_SYSTEM"` ([HANDOFF](../../../HANDOFF.md)).
- Wzorce różnią się źródłem: #1 używa MLPZ, #5 PESEL, a standard mówi MLPZ. Mentorzy nie rozstrzygnęli tego pytania (MLPZ kontra PESEL).

## Decyzja
- Generator zapisuje tylko konfigurację: źródło i atrybut w `defaultValue`. Wartości wypełnia system zewnętrzny przy wypełnianiu e-formularza. Nasza aplikacja niczego nie wstawia.
- Dane inicjalne są tylko w szablonie („Twoje dane”, adres, kontakt). Pola osób trzecich nigdy ich nie dostają.
- Domyślne źródło tożsamości: MLPZ. PESEL jako opcja konfiguracji.

## Konsekwencje
- Status „proponowana”: wybór MLPZ czy PESEL czeka na mentorów, a generator ma to jako pytanie nr 5 ([generator](../design/generator.md)).
- Kontakt z prefillem MLPZ zostaje edytowalny, jak we wzorcach, wbrew regule „dane inicjalne = readOnly”. To pytanie bez odpowiedzi.
- Nie sprawdzimy, czy źródło zwróci dane, bez integracji z MLPZ lub PESEL. Test odbywa się tylko na poziomie JSON.
