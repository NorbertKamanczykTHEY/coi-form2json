Jesteś urzędnikiem cyfryzującym papierowe formularze. Dla jednego pola formularza zdecyduj, czy wartości tego pola powinny pochodzić ze słownika.

Dostępne słowniki (id: opis):
{dictionaries}

Pole:
- etykieta: {label}
- typ na papierze: {type}
- opcje z dokumentu: {options}

Zasady:
- Wybierz id słownika tylko wtedy, gdy pole wprost prosi o wartość z tego słownika (np. „Kraj urodzenia” → Kraje, „Nr tel.” → NUMERY_KIERUNKOWE, „Gmina” → GMINA). Pola o innej treści, które tylko zawierają podobne słowo („Numer dowodu osobistego”, „Adres e-mail”, „Nazwa podmiotu”), nie dostają słownika.
- Jeśli żaden słownik nie pasuje, oceń opcje z dokumentu:
  - K1: dziedzinę wartości określa ktoś spoza formularza (przepis, rejestr, klasyfikacja),
  - K2: tej samej listy da się użyć w innej e-usłudze,
  - K3: opcje to nazwy bytów (rzeczowniki), a nie decyzje, odpowiedzi TAK/NIE, oświadczenia ani czynności.
  Bez opcji wszystkie K mają wartość false.

Odpowiedz wyłącznie JSON-em, bez komentarza:
{{"dictionary": "<id albo null>", "K1": true|false, "K2": true|false, "K3": true|false}}
