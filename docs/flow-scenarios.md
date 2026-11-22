# Scenariusze, role osób i decyzje mentorów

Przeniesione z przeglądu flow z 2026-11-21 (`research/2026-11-21-flow-review.md`, poza repozytorium): odpowiedzi mentorów, ustalenia U1–U6, scenariusze S1–S17 i role osób. Pozostałe sekcje przeglądu są na końcu jako historyczne.

Hierarchia źródeł przy konflikcie: Standardy COI > wzorce #1 i #5 > nasze ADR-y ([ADR 0023](adr/0023-wzorce-ponad-schemat.md)). Reguły są ogólne, wynikają z treści formularza, nie z jego numeru ([ADR 0024](adr/0024-uniwersalne-reguly-bez-poprawek-pod-formularz.md)). Przykłady z numerami formularzy pokazują tylko, skąd reguła się wzięła.

Aktualizacja 2026-11-22: model LLM działa przez Eden (OCR skanów to Tesseract + drabina VLM, nie PaddleOCR; [ADR 0007](adr/0007-t0-lokalnie-skany-do-vlm.md), [ADR 0010](adr/0010-adapter-dostawcy-modeli-i-air-gap.md)). P3 (opcja „Prezydent Miasta” w #9) rozstrzyga [ADR 0026](adr/0026-wnioskodawca-tylko-podmiot.md), pola wyliczane [ADR 0019](adr/0019-bez-pol-wyliczanych.md), #9 [ADR 0020](adr/0020-formularz-9-jeden-formularz.md).

## Odpowiedzi mentorów (2026-11-21)
| Temat | Odpowiedź | Skutek |
|---|---|---|
| LLM (P6, M4) | Organizator daje zestaw modeli LLM. Na obronie LLM działa przez **Eden LLM** | Klient LLM z konfigurowalnym endpointem i modelem (`coi/llm.py`, protokół OpenAI). Modele wizyjne i tekstowe z rodziny Mistral przez Eden; tryb air gap z lokalnym serwerem (`LLM_PROVIDER=local`) |
| Obligatoryjność (M2, P5) | **Domyślnie required** | R1 potwierdzone. Opcjonalne tylko przez R2 i R4. Każde pole dostaje `validation: ["REQUIRED", …]`, chyba że jest opcjonalne |
| Pola wyliczane (M1, P2) | JSONata w `states` zwraca **tylko true/false** | Nie ma wyliczania. #8 E i #6: użytkownik wpisuje dane wejściowe i wynik (NUMBER), stawki i wzór podajemy w `description` (decyzja autora) |
| #9 (M3, P1) | **Jeden plik → jeden formularz** | Jeden JSON. Radio „rodzaj wniosku” + sekcje ze SHOW. Wspólne sekcje raz |

Stan otwartych wtedy kwestii (2026-11-22):
- Nazwy techniczne słowników: `WOJEWODZTWO`, `POWIAT`, `GMINA`, `MIEJSCOWOSC`, `NUMERY_KIERUNKOWE`; `TERYT_DOWODOWY` to alias `TERYT_4G_DOWODOWY` ([dictionaries.md](dictionaries.md)).
- Forma nowego słownika: tylko z listą pozycji i tylko w raporcie ([ADR 0021](adr/0021-nowy-slownik-tylko-z-lista-pozycji.md), [ADR 0025](adr/0025-propozycje-slownikow-tylko-w-raporcie.md)).
- „Prezydent Miasta” w #9: odpada, wnioskodawca tylko podmiot ([ADR 0026](adr/0026-wnioskodawca-tylko-podmiot.md)).
- MLPZ kontra PESEL: konfiguracja `GENERATOR_PREFILL_IDENTITY` (domyślnie MLPZ).
- Python i obraz OCR: Python 3.14, bez osobnego kontenera OCR (Tesseract w obrazie backendu, [ADR 0007](adr/0007-t0-lokalnie-skany-do-vlm.md)).
- Nadal bez rozstrzygnięcia: warunkowe przejścia między stronami (schemat ich nie ma, `flow.links` liniowe), biblioteka sekcji, `minItemRows`.

## 0. Ustalenia, które zmieniają flow

| # | Ustalenie | Dowód |
|---|---|---|
| U1 | **Gwiazdka nigdy nie oznacza pola wymaganego.** Oznacza „niepotrzebne skreślić” albo przypis | #4 `wynajęcie/użyczenie*` + `* niepotrzebne skreślić`; #7 `/* niepotrzebne skreślić/ /**Opcjonalnie/`; #5 `PESEL *` / `NIP *` z przypisem „PESEL wpisują osoby fizyczne…, NIP pozostali” |
| U2 | Wzorce mają `validation: []` we **wszystkich** polach | #1: 57+5+5+2 pól, 0 walidacji; #5 tak samo |
| U3 | Strona „Dane” jest **identyczna** w #1 i #5 (12 sekcji, pełny zestaw podmiotów). Różni się tylko nagłówkiem urzędu lub organu i źródłem prefillu (MLPZ w #1, PESEL w #5) | zrzut obu JSON-ów |
| U4 | `flow.links` = `{id, source, target}`, bez warunku. `tabs` nie mają `states` | schemat i oba wzorce: liniowy łańcuch 4 linków |
| U5 | Schemat nie obsługuje **pól wyliczanych**, a #8 (część E) to arkusz kalkulacyjny | `liczba × stawka = opłata`, `SUMA poz. 38, 41, 44 i 47 pomniejszona o 50` |
| U6 | `multiLevelTree: true` występuje tylko przy TERYT, więc słowniki hierarchiczne są obsługiwane | `adres_zamieszkania / TERYT_4G_DOWODOWY` |

---

## 1. Scenariusze: papier → szablon czy przedmiot wniosku

Kryterium pierwszego rzędu: **czyje są dane i czy standard ma na nie sekcję**.

| ID | Sygnał na papierze | Przykład | Wynik w e-formularzu |
|---|---|---|---|
| S1 | Adresat „Wójt / Burmistrz / Prezydent” | #1 `Wójt Gminy Elbląg`, #4 `WÓJT GMINY PŁOSKINIA`, #8 `Prezydent Miasta Gdyni` | sekcja **„Organ, do którego…”** z polem „Nazwa organu” (readOnly, default = nazwa). Zgodne ze wzorcem #1 |
| S1b | Adresat „Urząd …” | #5 `Urząd Gminy Ulan-Majorat`, #3, #7 `Urząd Miejski Wrocławia Wydział Środowiska` | sekcja **„Urząd, do którego…”**, „Nazwa urzędu” (z wydziałem, jeśli podany) |
| S2 | Wnioskodawca wyłącznie jako osoba fizyczna (imię, nazwisko, PESEL, bez nazwy firmy) | #3, #4, #7 | Podmiot wniosku: **Swoim / Innej osoby**. Bez „Dane podmiotu” i bez radia „jako kto” |
| S3 | „imię i nazwisko / nazwa”, NIP, REGON | #1, #2 `Nazwa /Imię i nazwisko` + NIP, #5, #6 `lub nazwa firmy`, #8 `Nazwa pełna` + NIP/REGON | wszystkie 3 opcje + Pełnomocnik/Reprezentant. Tak jak oba wzorce |
| S4 | Wnioskodawca tylko jako podmiot | #9 `Wnioskodawca: Prezydent Miasta / Klub sportowy` + „Dane reprezentanta z KRS” / „Dane pełnomocnika” | tylko „Osoby prawnej…” + radio Pełnomocnik/Reprezentant. „Dane klubu” → „Dane podmiotu”. **Opcja „Prezydent Miasta” odpada (P3)** |
| S5 | Dane pełnomocnika na papierze | #2 `2.4 Dane pełnomocnika` | **odwrócenie ról**: zalogowany *jest* pełnomocnikiem, więc jego dane trafiają do „Twoje dane”, a dane wnioskodawcy z papieru do „Dane innej osoby” lub „Dane podmiotu”. Pola 2.4 usuwamy |
| S6 | Adres wnioskodawcy (dowolny układ) | #2 2.2, #7 A, #8 B.3 (Kraj/Woj./Gmina) | preset adresu ze standardu (Kraje + TERYT, stany PL/zagranica). Pola z papieru usuwamy |
| S7 | Telefon, e-mail wnioskodawcy | #1, #2 2.3, #3, #4, #6, #7, #8 F, #9 | strona „Kontakt i zgody” → „Dane do kontaktu” (opcjonalne, MLPZ). Z przedmiotu usuwamy |
| S8 | Adres korespondencyjny „jeśli inny” | #8 B.4, #9 `jeśli różni się od adresu zameldowania` | preset adresu + checkbox „Adres korespondencyjny jest inny” + SHOW |
| S9 | **Dane innej osoby, której dotyczy sprawa** | #8 B.2 współmałżonek, #9 sportowiec, trener i podopieczni, #4 osoba odpowiedzialna, #6 wykonawca i kierownik robót, #2 właściciel rachunku | **przedmiot wniosku**. Presety pól (imię, nazwisko, PESEL z walidatorem, preset adresu) **bez prefillu** |
| S10 | Elementy do usunięcia | „miejscowość, dnia”, podpisy (#8 ma 3), „wypełnia organ” (#7 nr sprawy, #8 I), instrukcja wypełniania (#2 pkt 1 „WIELKIMI LITERAMI”), podstawa prawna (#2 pkt 6, #5 art. 75), adres urzędu, pełna klauzula RODO | usunąć. Klauzula RODO → zgoda z linkiem (standard) |
| S11 | Oświadczenia i zgody | #4 (4 punkty), #7 (3), #6 `Wyrażam zgodę…`, #9 5.x i 6.x | CONSENT_SECTION na stronie „Kontakt i zgody”, `required: true`, treść w formie neutralnej płciowo (`zapoznałem/am` → „Zapoznaję się…”) |
| S11b | Zgoda zależna od wieku | #9 `5.1 kandydat pełnoletni` / `5.2 w imieniu nieletniego` | radio „Czy kandydat jest pełnoletni?” + SHOW na dwóch zestawach zgód. Z daty urodzenia tego nie wyliczymy (U5) |
| S12 | Lista załączników | #5 `korekta deklaracji` → wzorzec: FILE_UPLOADER „Plik deklaracji podatkowej”, #6 (6 pozycji), #8 G | FILE_UPLOADER na każdą pozycję, w przedmiocie. Pełnomocnictwo i opłata skarbowa → szablon, z listy usuwamy. Puste sloty `2) ___ 3) ___` (#5) wzorzec pomija |
| S12b | Załącznik warunkowy | #6 `projekt organizacji ruchu, jeżeli…`, #8 `zał. A lub B, jeśli TAK w poz. 34` | FILE_UPLOADER + SHOW (gdy warunek jest polem) albo opis w `description` (gdy warunek jest poza formularzem, jak w #6) |
| S13 | Puste miejsce przy opcji | #5 `zaliczyć na poczet… z tytułu ___` / `zwrócić przelewem ___` → wzorzec: RADIO + 2 pola SHOW; #3 `inne___`; #2 `Przelewem… wpisz nr rachunku` | RADIO lub CHECKBOX + pole zależne ze SHOW. **Najczęstszy wzorzec zależności** |
| S14 | Alternatywy „/” z `*` | #4 `wynajęcie/użyczenie*`, #7 `hodowanie/utrzymywanie*`, `charta/chartów*` | RADIO (wymagane) |
| S15 | Wartości stałe na papierze | #8 D.1 `Miejscowość GDYNIA`, stawki `38 zł`, #3 „opłata 17 zł, konto…” | readOnly + defaultValue albo TEXT_BLOCK z informacją |
| S16 | Pola wyliczane | #8 E.1–E.4, #6 `razem m2`, `Całkowita powierzchnia` | **brak wsparcia w schemacie (P2)** |
| S17 | Błąd w źródle | #7 tytuł „psy agresywne”, treść o chartach (Prawo łowieckie) | trzymać się tytułu i celu wniosku, w raporcie zgłosić niespójność |

### Role osób: dane inicjalne czy dane wpisywane
O tym, w czyim imieniu składa się wniosek, decyduje **obywatel w trakcie wypełniania** (radio „Wybierz, w czyim imieniu wnioskujesz”), a nie generator. Generator robi dwie rzeczy:
1. dobiera opcje radia (S2: Swoim / Innej osoby; S3: + osoba prawna; S4: tylko osoba prawna);
2. każdemu blokowi danych osobowych z papieru nadaje **rolę**.

| Rola | Kto to | Gdzie w e-formularzu | Dane inicjalne? |
|---|---|---|---|
| R-osoba-wypełniająca | zalogowany użytkownik, zawsze; we własnym imieniu albo jako pełnomocnik lub reprezentant | „Twoje dane” + „Adres zamieszkania” + „Dane do kontaktu” | **tak** (MLPZ/PESEL); tożsamość readOnly, adres i kontakt edytowalne (jak we wzorcach) |
| R-reprezentowany | wnioskodawca z papieru, gdy wybrano „Innej osoby” | „Dane innej osoby” + „Adres zamieszkania innej osoby”, SHOW | **nie**, wpisywane |
| R-podmiot | firma lub instytucja, gdy wybrano „Osoby prawnej…” | „Dane podmiotu” + „Adres siedziby”, SHOW | **nie** (MLPZ `institutionName` pomijamy, bo standard zakłada, że loguje się tylko obywatel) |
| R-osoba-trzecia | osoba, której dotyczy sprawa, ale która nie składa wniosku: współmałżonek (#8 B.2), sportowiec lub trener (#9), osoba odpowiedzialna (#4), wykonawca (#6), właściciel rachunku (#2), poprzedni właściciel psa (#7) | przedmiot wniosku, presety pól **bez prefillu** | **nigdy** |

Blok „Dane wnioskodawcy” z papieru **nie tworzy** pól: rozkłada się na szablon (wiersze 1–3) i znika z przedmiotu. Klasyfikujemy tylko, czy blok osobowy to wnioskodawca (→ szablon), pełnomocnik (→ szablon, S5), czy osoba trzecia (→ przedmiot).

Przypadek do decyzji: #8 „współwłaściciel (wspólność majątkowa)”. Współmałżonek jest współskładającym i na papierze podpisuje deklarację (poz. 78). W e-formularzu podpisuje tylko zalogowany, więc dane współmałżonka wpisujemy ręcznie (R-osoba-trzecia). Nie wiadomo, czy potrzebne jest jeszcze jego upoważnienie (pytanie do mentorów).

### Sprawdzenie na wzorcach
- #1: papier ma 3 pola przedmiotu (miejscowość, ulica, nr działki + obręb). JSON ma sekcję „Lokalizacja budynku” z 4 polami TEXT_FIELD. Reszta to S1, S3, S7 i S10. ✔
- #5: papier → JSON: `rodzaj podatku` TEXT_FIELD, `kwota` NUMBER, `uzasadnienie` TEXTAREA (opis przepisany), S13 (radio + 2 pola SHOW), S12 (1 plik). ✔

---

---

# Dalsze sekcje przeglądu z 2026-11-21 (historyczne)

Poniżej bez zmian: pytania do mentorów, słowniki, podział na strony, obligatoryjność (R1–R7) i pytania P1–P6. ADR-y odwołują się do nich numerami (pkt 4, pkt 6, P2, P5). Rozstrzygnięcia: odpowiedzi mentorów na górze tego pliku i ADR-y 0018–0027; aktualne słowniki: [dictionaries.md](dictionaries.md).

## 3. Pytania do mentorów (zbiorczo)

Szczegóły i fragmenty plików są w sekcji „Pytania (P)” na końcu dokumentu.

**M1. Pola wyliczane (P2).** Schemat nie ma formuł (`states`: SHOW i READ_ONLY, `defaultValueType`: tylko EXTERNAL_SYSTEM), a #8 część E to obliczenia (`liczba × stawka = opłata`, `SUMA poz. 38, 41, 44 i 47 pomniejszona o 50`), podobnie #6 (`długość × szerokość = razem m²`).
- Czy Generator Formularzy liczy cokolwiek po stronie e-usługi, np. JSONatą w `defaultValue`?
- Jeśli nie, które podejście jest oczekiwane: (a) użytkownik wpisuje wynik sam (NUMBER + stawka w opisie), (b) zbieramy tylko dane wejściowe (liczba gospodarstw), a kwotę liczy urząd, (c) pole wyliczane pomijamy?

**M2. Obligatoryjność (P5).** Wzorce #1 i #5 mają `validation: []` we wszystkich polach, a reguły techniczne mówią „każde pole musi mieć określony atrybut obligatoryjności”, standard zaś opisuje pola jako „Walidacja: pole wymagane”.
- Czy puste `validation` we wzorcach to uproszczenie, a oczekiwany wynik to `["REQUIRED", …]`?
- Czy pole opcjonalne zapisujemy jako `validation: []`, czy ma osobny znacznik?
- Czy REQUIRED na polu ukrytym przez SHOW jest sprawdzane tylko wtedy, gdy pole jest widoczne?

**M3. #9: jeden formularz czy trzy, i ponowne użycie sekcji (P1, P3).** Folder nazywa się *„(Połączenie 3 wniosków w 1)”*, ale zadanie 3.3.III mówi o przepływach „między stronami”, a `flow.links` nie ma warunku. Wnioski I–III mają wspólną większość treści:

| Blok | I stypendium | II nagroda | III wyróżnienie |
|---|---|---|---|
| Wnioskodawca (Prezydent / Klub), reprezentant / pełnomocnik, dane klubu, korespondencja, odpis KRS | ✔ | ✔ | ✔ |
| Dane kandydata (imię, nazwisko, data urodzenia, adresy) | sportowiec | sportowiec | trener |
| Dyscypliny sportowe | ✔ | – | – |
| Osiągnięcia, opinia klubu, dodatkowe informacje | ✔ | ✔ | opinia + dodatkowe |
| Podopieczni trenera (×4) | – | – | ✔ |
| Zgody: pełnoletni / nieletni | ✔ | ✔ | kandydat + podopieczni |

Pytania:
- Czy oczekiwany jest **jeden JSON** (radio „rodzaj wniosku” + sekcje SHOW), czy **trzy osobne JSON-y**?
- Jeśli jeden: czy wspólne sekcje mają być **zdefiniowane raz** i współdzielone przez warianty (jeden `techName`, jedna JSONata), czy dopuszczalne są kopie dla każdego wariantu?
- Czy Generator Formularzy ma **bibliotekę sekcji predefiniowanych** (standard, pkt 10: „Korzystaj z sekcji predefiniowanych”), do której JSON może się odwołać, czy każda sekcja musi być wpisana w całości z własnym UUID?
- Jak zapisać warunkowy przepływ stron, skoro link to tylko `{id, source, target}`?
- Czy opcja „Wnioskodawca: Prezydent Miasta Zgierza” zostaje w e-formularzu (P3)?

**Nasza propozycja na wypadek braku odpowiedzi:** jeden JSON. Wspólne sekcje definiujemy raz, a różnice między wariantami pokazujemy przez SHOW zależne od radia „rodzaj wniosku”. Po stronie generatora mamy bibliotekę szablonów sekcji (nasz kod), więc trzy osobne JSON-y też da się wygenerować z tych samych definicji.

**M4. Modele przez API i OpenRouter (P6).**

---

## 4. Słowniki: czego oczekują dokumenty i gdzie występują

**Co mówi dokumentacja (wszystkie wzmianki):**
- Pełna treść zadania, 3.3.II: *„Zaproponowanie nowego słownika, jeżeli w bazie danych wejściowych brakuje odpowiedniego słownika, do zasilania wybranych pól w formularzu elektronicznym.”* W kryteriach jako osobny próg: „Punkt II (Nowy słownik)”.
- Słowniki.docx: *„Jeżeli podczas analizy formularzy widzisz możliwość zastosowania innego nowego słownika – zaproponuj jego **nazwę, strukturę i zastosowanie** w formularzu (opcjonalne rozszerzenie).”* Ten sam dokument definiuje słownik jako „gotowy, predefiniowany zestaw odpowiedzi”, z którego użytkownik „wybiera konkretną pozycję”.
- Reguły techniczne i Opis JSON: tylko `dictionaryName` („nazwa predefiniowanego słownika”), `options: []` przy słowniku, tylko SELECT, RADIO i CHECKBOX (Kraje i TERYT wyłącznie SELECT).
- Zadanie, pkt 3.3: docelowym użytkownikiem jest **urzędnik** cyfryzujący formularze.

**Wniosek:** dokumentacja wymaga nazwy, struktury i zastosowania. **Nie wymaga listy pozycji** i nie zabrania propozycji bez niej. Założenie „bez listy nie tworzymy” jest więc **naszą decyzją**, nie wymogiem. Decyzja jest rozsądna: brak halucynacji i deterministyczny wynik.

**Przyjęta reguła (2026-11-21):** nowy słownik powstaje tylko wtedy, gdy mamy listę pozycji:
1. lista jest w dokumencie (#9 dyscypliny: 3 rodzaje + 20 pozycji), albo
2. lista jest w naszym katalogu przygotowanym offline z tekstów źródłowych (np. wykaz ras z rozporządzenia, po weryfikacji).

Bez listy: pole zostaje TEXT_FIELD lub `options` (#7 „Rasa psa”, jeśli rasy nie trafią do katalogu).

Schemat ma tylko `dictionaryName: string`. Format propozycji jest nasz (P4).

### Wystąpienia w formularzach

| Formularz | Pole | Na papierze | Decyzja |
|---|---|---|---|
| wszystkie z adresem | kraj, województwo, gmina, miejscowość | tekst albo osobne pola (#8 B.3) | istniejące: Kraje, TERYT_4G_DOWODOWY |
| wszystkie z telefonem | numer telefonu | tekst | istniejące: Numery kierunkowe (wzorce go **nie używają**) |
| **#9** | dyscypliny sportowe | 3 rodzaje (`zespołowa / indywidualna – inna / indywidualna – lekkoatletyka`) + 20 dyscyplin + `Inna ___` | **nowy: DYSCYPLINY_SPORTOWE**, 2 poziomy (`multiLevelTree`), `searchEnabled` (>15), „Inna” → pole SHOW |
| **#7** | rasa psa | `Rasa psa: ___` (wolny tekst) | **nowy: RASY_PSOW_AGRESYWNYCH**. Lista **nie występuje w dokumencie**: to zamknięty wykaz z rozporządzenia MSWiA z 28.04.2003 (11 ras, do potwierdzenia) |
| **#9** | sposób korespondencji | `Poczta tradycyjna / Skrzynka ePUAP / eDoręczenia` | **nowy: SPOSOBY_DORECZENIA**, wspólny dla wielu usług, powiązany z walidatorami EPUAP i ADE |
| #5, #2 | rodzaj podatku lub opłaty | `(rodzaj podatku) ___` | kandydat: RODZAJE_PODATKOW_LOKALNYCH. Wzorzec #5 użył TEXT_FIELD, więc słownik to opcjonalny bonus |
| #8 | składający (6 opcji) | radio | `options`: lista z ustawy, ale specyficzna dla tej deklaracji |
| #3, #4, #7, #8 | rodzaje zaświadczeń, cel wynajmu, płeć psa, oznakowanie, TAK/NIE | radio, checkbox | `options` |

### Kryteria (wyprowadzone z tych przykładów)
- **K1** Dziedzinę wartości określa ktoś spoza formularza: przepis, rejestr, klasyfikacja (rasy, dyscypliny, kraje, podatki).
- **K2** Tej samej listy da się użyć w innej e-usłudze.
- **K3** Wartości to nazwy bytów (rzeczowniki), a nie decyzje lub czynności („zaliczyć / zwrócić”, „Tak / Nie”).
- **Decyzja:** K1 ∧ K2 ∧ K3 → słownik. Liczba opcji decyduje tylko o komponencie: >5 → SELECT, >15 → `searchEnabled`.
- Rasy koni: K1 tak (księgi stadne), K2 tak, K3 tak → propozycja słownika, nawet gdy papier ma wolne pole tekstowe.

### Wykonanie w runtime
1. **Katalog znanych słowników** przygotowany offline przed obroną (istniejące + nasze propozycje: nazwa, poziomy, pozycje, aliasy etykiet). Dopasowanie aliasem lub fuzzy.
2. Brak dopasowania → LLM-sędzia zwraca `{K1, K2, K3: bool, uzasadnienie}`, a nie procent. Wszystkie trzy `true` **i lista pozycji w dokumencie** → propozycja nowego słownika. Bez listy nie ma propozycji (reguła wyżej). Lokalny LLM nigdy nie wymyśla pozycji.

```json
{ "name": "DYSCYPLINY_SPORTOWE", "multiLevel": true,
  "levels": ["rodzaj", "dyscyplina"],
  "items": [{ "name": "zespołowa", "children": ["hokej", "koszykówka", "piłka nożna", "…"] }],
  "usedIn": [{ "techName": "dyscypliny_sportowe", "type": "SELECT" }],
  "source": "document", "confidence": "K1,K2,K3" }
```

---

## 5. Czy da się logicznie wydzielać strony? Tak, prawie deterministycznie

Szkielet jest stały: `Dane` (szablon) → **[strony przedmiotu]** → `Kontakt i zgody` → FINISH. Dzielić trzeba tylko przedmiot.

**Reguły:**
1. Kandydaci na strony to nagłówki najwyższego poziomu z papieru (`A–I` w #8, `1–8` w #2, `A/B` w #7, `I–III` w #9).
2. Usuwamy nagłówki zmapowane na szablon (S1–S8) i do usunięcia (S10, S11).
3. Pozostałe bloki: < 3 pola → doklejamy do sąsiedniego jako sekcję, ok. 3–12 pól → strona, > 12 → dzielimy po podnagłówkach. Progi są naszą decyzją, standard ich nie podaje.
4. Tytuł strony bierzemy od treści („Informacje o budynku”, „Informacje o nadpłacie”). Pozwala na to pkt „Druga i kolejne strony” standardu.
5. Sekcja powtarzalna, gdy papier mówi to wprost (#7 `w przypadku więcej niż jednego psa pobrać odpowiednią liczbę załączników z tabelą B`) albo numeruje identyczne bloki (#9 `1.–4. Dane osobowe podopiecznego trenera`).
6. Strony alternatywne emulujemy sekcjami ze SHOW (U4, P1).

**Wynik dla formularzy:**

| # | Strony przedmiotu |
|---|---|
| 1 | Informacje o budynku (wzorzec ✔) |
| 5 | Informacje o nadpłacie: 3 sekcje (wzorzec ✔) |
| 2 | Informacje o opłacie: Opłata, Uzasadnienie, Sposób zwrotu (S13), Załączniki |
| 3 | Rodzaj zaświadczenia: checkboxy + „inne” (S13) + cel |
| 4 | Informacje o wynajmie: wynajem/użyczenie (S14), termin od–do, cel, liczba uczestników, osoba odpowiedzialna (S9) |
| 6 | Zakres zajęcia pasa (droga, działka, roboty, 4 × długość/szerokość) · Termin i wykonawca · Załączniki |
| 7 | Informacje o psie: REPEATING_SECTION · Miejsce utrzymania |
| 8 | Okoliczności (C) · Nieruchomość (D) · Wysokość opłaty (E, P2) · Załączniki (G). B.2 współmałżonek jako sekcja SHOW przy opcji „współwłaściciel (wspólność majątkowa)” |
| 9 | Rodzaj wniosku (radio I/II/III) · Dane sportowca lub trenera · Osiągnięcia i opinia · Podopieczni (REPEATING, tylko III). Sekcje SHOW według rodzaju |

---

## 6. Obligatoryjność: zasady z dokumentów

**Liczby:** gwiazdki występują w #3 (1), #4 (2), #5 (2) i #7 (12). Żadna nie oznacza „wymagane” (U1). Wzorce nie podpowiadają nic (U2).

**Jawne znaczniki opcjonalności:** #2 `dane kontaktowe nie są obowiązkowe`, #7 `**Opcjonalnie` (metryka, nr rodowodu), #8 `F. DANE DO KONTAKTU (pola nieobowiązkowe)`, #9 `(opcjonalnie)` ×9 (telefony), #9 `Ewentualne dodatkowe informacje`.

**Zasady:**
- **R1** Domyślnie pole jest wymagane. Papierowy formularz zbiera dane potrzebne do sprawy, a reguła mówi, że każde pole ma określoną obligatoryjność.
- **R2** Opcjonalne, gdy pole ma znacznik: „opcjonalnie”, „nieobowiązkowe”, `**`, „ewentualne”, „dodatkowe informacje”, „uwagi”. Dane kontaktowe są opcjonalne zawsze (standard).
- **R3** Warunkowe (wymagane + SHOW): „wypełnić tylko w przypadku…” (#8 B.2, B.4, E.3), „jeśli różni się” (#9), „jeśli wybierzesz tę formę” (#2), pole przy opcji (S13).
- **R4** Załączniki: „**należy** dołączyć/załączyć” → wymagany; „**można** dołączyć” → opcjonalny. #9 ma oba warianty obok siebie (zaświadczenia PZS kontra dyplomy).
- **R5** Grupa alternatyw (S14) lub lista „Proszę o…” (#3) → RADIO/CHECKBOX wymagane.
- **R6** Pola z szablonu dostają obligatoryjność według standardu (KRS opcjonalny, „Brak numeru lokalu” itd.).
- **R7** Zostaje niejasne → wymagane + flaga `low_confidence`. Przykład: #7 `Data szczepienia (w przypadku jego braku)` nie wiadomo, czego dotyczy „jego braku”.

Przy R1 i R7 wątpliwości dotyczą tylko kilku pól na formularz. Większość decyzji wynika z R2–R4, które są zwykłym dopasowaniem wzorców tekstu.

---

## Pytania (P)

**Status (2026-11-21):** P1, P3 i P6 do mentorów · P2 rozstrzygnięte (brak obliczeń) · P4 tak (rozszerzone) · P5 tak.

### P1. Strony alternatywne (#9) przy flow bez warunków
Do mentorów. Argumenty do rozmowy:
- folder ma w nazwie *„(Połączenie 3 wniosków w 1)”*, co sugeruje jeden formularz;
- zadanie 3.3.III mówi o *„dynamicznych przepływach między polami, sekcjami **i stronami**”*, a schemat linku nie ma warunku. Trzeba zapytać, jak zapisać warunkowy przepływ stron.

Wzorzec #1:
```json
"flow": {"links": [
  {"id": "fbc1…", "source": "7d4c…(Dane)", "target": "4553…(Informacje o budynku)"},
  {"id": "8e8b…", "source": "4553…", "target": "c7cb…(Kontakt z urzędem)"},
  {"id": "cc11…", "source": "c7cb…", "target": "a44a…(Strona końcowa)"}]}
```
Schemat linku: `{id, source, target}`, bez warunku. Strona nie ma `states`.
- **A (polecam):** jedna strona „Rodzaj i dane kandydata” z radiem I/II/III, sekcje z `SHOW`. Działa w obecnym schemacie.
- **B:** kilka linków z jednej strony. Nie wiadomo, jak generator wybiera gałąź. Bez potwierdzenia mentorów to ryzyko.

### P2. Pola wyliczane (#8 E, #6 „razem m²”)
```
36. Liczba gospodarstw domowych … nie przekraczającej 45 m²  X  37. Stawka 38 zł  =  38. Wysokość miesięcznej opłaty ___ zł
51. SUMA poz. 38, 41, 44 i 47 pomniejszona o kwotę z poz. 50
```
**Rozstrzygnięte: schemat nie ma wyliczania.** Pełna lista właściwości schematu: `cols, consentSectionConfig, consents, defaultValue, defaultValueType, description, dictionaryName, field, files, flow, id, links, name, options, query, questionOrder, questions, readOnly, repetingSectionGrid, required, rows, source, states, tabs, target, techName, title, tooltipMessage, type, validation, x, y`. Wzorce dokładają tylko `minItemRows, multiLevelTree, repeatingSectionGrid, searchEnabled`. `states.type` to SHOW lub READ_ONLY. `defaultValueType` zna tylko EXTERNAL_SYSTEM. Treść zadania nie wspomina o obliczeniach.
- **A (polecam):** użytkownik wpisuje liczby gospodarstw (NUMBER). Stawki podajemy w TEXT_BLOCK, a kwotę wpisuje sam w osobne pole NUMBER z opisem „liczba × stawka”.
- **B:** pytamy mentorów, czy JSONata w `defaultValue` jest obliczana.

### P3. #9: „Wnioskodawca: Prezydent Miasta Zgierza”
```
1. Wnioskodawca
   Prezydent Miasta Zgierza
   Klub sportowy
Należy wypełnić w przypadku Wnioskodawcy – Klubu sportowego.
```
Standard zakłada, że formularz wypełnia obywatel. Prezydent nie składa e-wniosku do samego siebie. **Polecam** usunąć tę opcję: wnioskodawcą jest klub działający przez reprezentanta lub pełnomocnika.

### P4. Gdzie oddajemy propozycję nowego słownika?
**Decyzja:** odpowiedź API = konfiguracja formularza + `proposedDictionaries[]`. Każdy wpis: `{id, name, structure (poziomy + pozycje), fields: [techName…]}`. W JSON-ie formularza pole ma `dictionaryName` i `options: []`. Do tego endpoint tworzący słownik z propozycji, który dopisuje go do katalogu, dzięki czemu kolejne formularze dopasują go już jako istniejący.

### P5. Wypełniamy `validation`, mimo że wzorce mają puste?
Reguła „każde pole ma określoną obligatoryjność” i próg V „walidacje” mówią: tak. Wzorce mówią: nie. **Polecam** wypełniać `["REQUIRED", …]` według R1–R7 i opisać to w README jako świadome odejście od wzorców.

### P6. Modele przez API: czy demo może korzystać z OpenRouter? (do mentorów)
Treść zadania, pkt 5 „Biblioteki i frameworki”:
```
•   Brak użycia zależności takich jak zewnętrzne API, MCP, SaaS itp.
•   W szczególności rozwiązanie nie może używać modeli LLM dostępnych
    wyłącznie przez API (ale można ich używać do pisania/testowania/projektowania
    kodu)
```
**Szara strefa:** model open-weights (np. Qwen, Bielik, Gemma) nie jest „dostępny wyłącznie przez API”, więc drugi punkt go nie wyklucza. Ale OpenRouter to zewnętrzne API i SaaS, a to wyklucza punkt pierwszy. Do tego finaliści uruchamiają rozwiązanie na żywo na nowych plikach, więc demo jest ocenianym runtime'em, a nie środowiskiem deweloperskim.

**Pytania do mentorów:**
1. Czy na obronie model open-weights może działać przez OpenRouter, jeśli to samo rozwiązanie da się uruchomić lokalnie (ten sam model, zmiana tylko `LLM_BASE_URL`)?
2. Czy wynikowe JSON-y dla #2–#9 (oddawane w zgłoszeniu) można wygenerować z modelem przez OpenRouter, czy muszą pochodzić z lokalnego runtime'u?
3. Jeśli tylko lokalnie: jaki sprzęt będzie na obronie (własny laptop czy maszyna organizatora, GPU czy CPU)?

**Niezależnie od odpowiedzi** klient LLM ma być zgodny z OpenAI (`base_url` + `model` z konfiguracji). Przełączenie OpenRouter ↔ lokalny serwer (llama.cpp server / Ollama / vLLM) to wtedy zmiana zmiennej środowiskowej, bez zmian w kodzie. Na OpenRouter używamy **wyłącznie modeli open-weights**, które uruchomimy też lokalnie, żeby wyniki nie zależały od tego, gdzie model działa.
