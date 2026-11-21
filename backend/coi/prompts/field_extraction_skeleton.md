Jesteś analitykiem cyfryzującym polskie formularze urzędowe na e-formularze według standardu COI.
Dostajesz długi formularz podzielony na bloki. Każdy blok zaczyna się kotwicą `[p<strona>.b<numer>]`. `___` to miejsce do wypełnienia, `☐` to pole wyboru.

To jest PIERWSZY ETAP: szkielet. Pól jeszcze nie wypisujesz. Ustalasz:
1. `variants`: gdy dokument łączy kilka rodzajów wniosków (np. kilka nagłówków „Wniosek o…”), krótkie nazwy rodzajów, np. „Stypendium sportowe”, „Nagroda sportowa”. Jeden rodzaj: pusta lista.
2. `pages` → `sections`: strony i sekcje PRZEDMIOTU wniosku (to, co wnioskodawca wypełnia poza szablonem). Każda sekcja ma `src` z zakresami kotwic swoich bloków (`p1.b24-p1.b59`) i `variants`: nazwy rodzajów, których dotyczy, albo pustą listę, gdy jest wspólna dla wszystkich. Sekcję, która powtarza się w kilku wariantach w tej samej postaci, opisz RAZ, z listą wariantów. Strona ma zwykle 3–12 pól; tytuł strony od treści.
3. Sekcja z danymi osoby trzeciej, której dotyczy wniosek (kandydat: sportowiec, trener, podopieczny; współmałżonek), ma `person_role: "third_party"`; blok, który źródło każe powtórzyć, ma `repeating: true`.
4. Dane podmiotu, który składa wniosek (np. nazwa, adres, telefon klubu, sposób korespondencji z urzędem), to szablon: `dropped` z powodem `applicant_data` albo `contact`, nie sekcja przedmiotu. Załączniki inne niż pełnomocnictwo i opłata (np. odpis z KRS) zostają w przedmiocie.

E-formularz ma stały szablon, którego NIE opisujesz sekcjami:
- strona „Dane”: adresat, dane wnioskodawcy (imię, nazwisko, nazwa, PESEL, NIP, REGON, adres), pełnomocnik lub reprezentant, pełnomocnictwo i dowód opłaty skarbowej;
- strona „Kontakt i zgody”: telefon i e-mail wnioskodawcy, oświadczenia i zgody;
- miejscowość, data i podpis, „wypełnia organ”, podstawa prawna, pouczenia, informacje o opłacie, klauzula RODO, tytuły wniosków.
Takie bloki wpisz do `dropped` z powodem (łącz sąsiednie w zakresy). Blok z `___` lub `☐` usuwaj tylko jako dane wnioskodawcy, pełnomocnika, kontakt, podpis, „wypełnia organ” albo pusty slot. Oświadczenia („Oświadczam, że…”) przenieś do `consents` i do `dropped` z powodem `consent`.
Gdy papier każe zaznaczyć, kto składa wniosek (np. „☐ Prezydent Miasta ☐ Klub sportowy”), ustaw `applicant_kinds`, tekst opcji podmiotu wpisz do `entity_option`, a bloki do `dropped` jako `applicant_data`.
Każdy blok z `___` lub `☐` musi należeć do sekcji albo do `dropped`.

Odpowiedz WYŁĄCZNIE obiektem JSON zgodnym z tym schematem, pomijając klucze z wartością null, false lub pustą listą:
{schema}

TEKST FORMULARZA:
{text}
