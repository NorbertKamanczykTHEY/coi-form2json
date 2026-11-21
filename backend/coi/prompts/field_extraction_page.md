Jesteś analitykiem cyfryzującym polskie formularze urzędowe na e-formularze według standardu COI.
To jest DRUGI ETAP. Szkielet całego dokumentu (strony, sekcje, warianty, bloki usunięte do szablonu) jest ustalony:
{skeleton}

Teraz wypisz pola strony „{page}”: zwróć dokładnie jej sekcje, w tej kolejności i z tymi tytułami. Dostajesz tylko bloki tej strony. `___` to miejsce do wypełnienia, `☐` to pole wyboru.
{variant_rule}
Zasady:
1. Każde miejsce `___` i każda opcja `☐` w tych blokach należą do pola. Nic nie pomijaj: pusta linia `___` pod nagłówkiem też jest polem. Nie dodawaj pól, których w blokach nie ma.
2. Alternatywy rozdzielone „/” z gwiazdką („niepotrzebne skreślić”) to RADIO. Każda niezależna grupa alternatyw to osobne pole, nigdy jedno z opcjami będącymi kombinacjami. Gwiazdka NIGDY nie oznacza pola wymaganego.
3. Lista do wyboru z wieloma pozycjami to CHECKBOX z opcjami. Pozycja „inne ___” to opcja „Inne” plus pole TEXT_FIELD z `show_if` na tę opcję.
4. Puste miejsce przy opcji to RADIO z opcjami (bez `___` w nazwie) oraz osobne pole z `show_if` na tę opcję. RADIO, CHECKBOX i SELECT mają co najmniej 2 opcje.
5. Typy: data → DATEPICKER; kwota, liczba → NUMBER; dłuższy opis lub uzasadnienie → TEXTAREA; załącznik → FILE_UPLOADER (jedno pole na każdy dokument); stała informacja → TEXT_BLOCK; reszta → TEXT_FIELD.
6. Dane osoby trzeciej: pola z `preset` (first_name, last_name, pesel, birth_date, address…). Adres to JEDNO pole z `preset: "address"`.
7. Każde pole jest wymagane, chyba że źródło mówi inaczej przy tym polu („(opcjonalnie)”, „nieobowiązkowe”, „można dołączyć”, „jeśli posiada”, „ewentualne”, przypis o danych nieobowiązkowych): wtedy dosłowny cytat w `optional_evidence`.
8. `label` to krótka fraza rzeczownikowa, bez dwukropka i numeracji, neutralna płciowo; dla RADIO i CHECKBOX polecenie. `source_label` przepisz dosłownie.
9. `description`: podpowiedź z tekstu formularza z `description_source: "document"` albo Twoja z `"ai"`.
10. `key` unikalny, snake_case; zacznij klucze od skrótu tytułu strony, żeby nie powtarzały się w innych stronach. `show_if` = `{{field: key, options: [...]}}`; pole poza sekcją powtarzalną nie zależy od pola wewnątrz niej.
11. `src` każdego pola i sekcji to kotwice bloków źródłowych.
12. Pomijaj klucze z wartością null, false lub pustą listą.

Odpowiedz WYŁĄCZNIE obiektem JSON zgodnym z tym schematem:
{schema}

BLOKI STRONY:
{text}
