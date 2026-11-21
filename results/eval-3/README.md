# EVAL-3: wszystkie formularze kontra interpretacja eksperta (HEAD c935629)

Przebieg: `app/results/run.py` na docker compose, obraz backendu zbudowany z HEAD c935629, 11 plików (#1–#9 edytowalne, #7 jpg, #9 png). Wszystkie przechodzą `POST /forms/validate` i schemat z `materials/`. **Łączny koszt Eden: $0.2467** (szczegóły w [../README.md](../README.md)).

Metoda: dla każdego formularza najpierw własna interpretacja papieru według Standardów, Reguł technicznych, Słowników, Danych inicjalnych, wzorców #1/#5, flow-review (S1–S17, R1–R7) i ADR-ów, potem porównanie z `<n>.coi.json`. Różnice szablonu identyczne we wzorcach #1/#5 nie są liczone. W kodzie nic nie zmieniono.

## Rozbieżności według wagi

| Formularz | Krytyczne | Średnie | Kosmetyczne | Koszt [$] | Plik |
|---|---|---|---|---|---|
| #1 numer porządkowy (wzorzec) | 0 | 0 | 1 | 0.0032 | [1.md](1.md) |
| #2 zwrot opłaty skarbowej | 2 | 3 | 1 | 0.0174 | [2.md](2.md) |
| #3 zaświadczenie | 0 | 3 | 3 | 0.0014 | [3.md](3.md) |
| #4 świetlica | 1 | 4 | 5 | 0.0095 | [4.md](4.md) |
| #5 nadpłata podatku (wzorzec) | 0 | 1 | 3 | 0.0038 | [5.md](5.md) |
| #6 pas drogowy | 2 | 5 | 4 | 0.0145 | [6.md](6.md) |
| #7 psy (doc) | 3 | 5 | 3 | 0.0035 | [7.md](7.md) |
| #8 deklaracja odpady | 11 | 4 | 5 | 0.0573 | [8.md](8.md) |
| #9 stypendium (docx) | 3 | 7 | 6 | 0.0666 | [9.md](9.md) |
| **Razem (edytowalne)** | **22** | **32** | **31** | 0.1772 | |
| #7 skan jpg (tylko dodatkowe) | +1 | +1 | +1 | 0.0097 | [7.md#skan](7.md) |
| #9 skan png (tylko dodatkowe) | +3 | +5 | +1 | 0.0599 | [9.md#skan](9.md) |

Wzorce #1 i #5 są praktycznie zgodne z oczekiwanym JSON-em. Błędy skupiają się w formularzach z alternatywami, warunkami i osobami trzecimi (#8, #9, #6, #7). Oba skany są gorsze od wersji edytowalnych: gubią oświadczenia (#7) i przenoszą blok wnioskodawcy do przedmiotu (#9).

## Reguły ogólne, posortowane po zysku

Zysk = liczba rozbieżności krytycznych (K), średnich (S) i kosmetycznych (C), które reguła usuwa, w nawiasie formularze. Każda reguła wynika z treści formularza, nie z jego numeru.

| # | Reguła (sygnał w treści → wynik) | Gdzie wdrożyć | Zysk | Dowody |
|---|---|---|---|---|
| G1 | **Pola wzajemnie wykluczające się nie mogą być REQ jednocześnie.** Sygnały: „A lub B”, „jeżeli…”, „W PRZYPADKU…”, „wypełniamy wyłącznie…”, kategorie, z których wybiera się jedną, zgody „pełnoletni / nieletni”. Wynik: RADIO wyboru + SHOW na każdej gałęzi. Gdy warunek jest poza formularzem: pole opcjonalne + warunek w `description`. Bramka odrzuca ≥2 wymagane pola bez rozłącznych SHOW, których źródło zawiera „lub / jeżeli / w przypadku”. Generator po obcięciu warunku nie zostawia REQ na obu gałęziach | prompt ekstrakcji + bramka + generator | **6 K** (#6, #8, #9; skan #9 +1 K) | 6.md rozb. 1–2, 8.md rozb. 3, 5, 7, 9.md rozb. 2, 9.md S3 |
| G2 | **Osoby trzecie i warunkowe bloki osobowe (S9).** Blok „wypełnić tylko w przypadku zaznaczenia poz. X” → sekcja osoby trzeciej ze SHOW na tej pozycji. Gdy osobą może być firma (wnioskodawca S3, etykieta „Dane właściciela” bez „imię i nazwisko”) → jedno pole „Imię i nazwisko lub nazwa”. Preset adresu (pełny, bez prefillu) tylko wtedy, gdy papier pyta o adres („zam.”, „adres”). Pole pełnomocnika spoza MLPZ (seria i numer dowodu) → sekcja „Pełnomocnictwo” | prompt ekstrakcji + szablon | **3 K** + 2 S (#2, #6, #8, #9) | 2.md rozb. 2–3, 6.md rozb. 6, 8.md rozb. 2, 9.md rozb. 3 |
| G3 | **Załączniki z treści.** „w załączeniu”, „należy dołączyć” → FILE_UPLOADER REQ (w sekcji powtarzalnej, gdy „dla każdego”). „można dołączyć” → opcjonalny FILE_UPLOADER, nie opis. Ten sam dokument w treści i na liście → jeden uploader. Pełnomocnictwo i „dokumenty upoważniające” usunąć (są w szablonie). „Inne (podać jakie)” → opcjonalny FILE_UPLOADER. Puste sloty „2) …… 3) ……” pominąć | prompt ekstrakcji + deduplikacja w generatorze | **3 K** + 1 S + 1 C (#5, #6, #7, #8; skan #9 +1 S) | 7.md rozb. 2, 8.md rozb. 8–9, 6.md rozb. 5, 5.md rozb. 2, 9.md S7 |
| G4 | **Oświadczenia i zgody.** „Oświadczam, że…” i „Jednocześnie oświadczam” → CONSENT_SECTION (nigdy TEXT_BLOCK ani osobna strona). Treść w czasie teraźniejszym, w stronie czynnej, bez „/am”, „/a”, form bezosobowych („zaszczepiono”) i literówek źródła. Zgoda RODO tylko z szablonu: zgoda z papieru o danych osobowych to dubel (usunąć), administrator różny od adresata → `warning`. Zgoda na kanał kontaktu (e-mail, SMS) ma `required: false`. Tytuł sekcji według zawartości | prompt zgód + bramka (regex `/am`, `/a\b`, „ochronie danych osobowych”, TEXT_BLOCK z „Oświadczenie … dotyczące”) | **2 K** + 5 S + 2 C (#4, #6, #7, #8, #9; skan #7 +1 K) | 4.md rozb. 1–2, 9, 6.md rozb. 7–8, 7.md rozb. 8 i S1, 8.md rozb. 10, 9.md rozb. 9–10 |
| G5 | **Opcje „Wybierz, w czyim imieniu wnioskujesz” to zamknięta lista ze Standardów.** Model wybiera tylko wariant (S2 / S3 / S4 / tylko osobiście), tekst opcji bierze generator. Radio o roli składającego z papieru (właściciel, najemca…) to osobne pole przedmiotu, nigdy opcja podmiotu. Blok wnioskodawcy z papieru nie trafia do przedmiotu. Bramka: opcja spoza listy → błąd | generator + bramka | **2 K**, każda psuje SHOW 5+ sekcji szablonu (#2, #8; skan #9 +1 K: opcja „Prezydent Miasta”) | 2.md rozb. 1, 8.md rozb. 1, 9.md S1 |
| G6 | **Typ pola z kształtu miejsca do wpisania.** Każda pozycja SUMA/RAZEM → NUMBER, wzór i stawka w `description` (ADR 0019), nie w TEXT_BLOCK z `defaultValue`. „od dnia … do dnia” → 2 × DATEPICKER. Kilka linii kropek, „podać jaki oraz dokładne dane” → TEXTAREA. „długość × szerokość = razem” w kilku kategoriach → REPEATING_SECTION (kategoria + NUMBER). Rachunek → opis „26 cyfr”, bez maski „XX…”. Data bez opisu-maski | prompt ekstrakcji + generator | **1 K** + 6 S + 1 C (#2, #6, #7, #8) | 8.md rozb. 11–12, 14, 6.md rozb. 3–4, 7.md rozb. 7, 2.md rozb. 5–6 |
| G7 | **Wybór „x/y*” z przypisem „niepotrzebne skreślić” → RADIO REQ (S14).** Stały tekst bez znaku wyboru nie staje się polem. Gdy przypis nie dotarł z parsera (stopka docx), bramka nie zgłasza G5 jako błędu | prompt ekstrakcji + bramka G3 + parser (stopki) | **1 K** + 1 S (#7, #4) | 7.md rozb. 1, 4.md rozb. 3 |
| G8 | **Opłata za samą sprawę** (kwota, konto, „płatne przed złożeniem”) → TEXT_BLOCK „Opłata” na stronie „Kontakt i zgody”, plik potwierdzenia, gdy papier go wymaga. Osobno od opłaty 17 zł za pełnomocnictwo | prompt ekstrakcji + generator | **1 K** + 1 S (#3, #7) | 7.md rozb. 3, 3.md rozb. 1 |
| G9 | **Wymagany CHECKBOX z jedną opcją** → RADIO Tak/Nie albo CHECKBOX opcjonalny. needs_review już to wykrywa, generator nie naprawia | generator | **1 K** (#8; skan #9 +1 K) | 8.md rozb. 4, 9.md S1 |
| G10 | **SHOW musi być rozstrzygalny w chwili wyświetlenia.** Warunek będący alternatywą wszystkich opcji pola wymaganego → usunąć (zawsze prawdziwy). Warunek na polu z późniejszej strony → przenieść pole-warunek wcześniej albo sekcję później | generator + bramka | **1 K** (#9) | 9.md rozb. 1 |
| G11 | **Adres w przedmiocie budowany jak preset:** „Numer lokalu” zawsze opcjonalny (Standardy: checkbox „Brak numeru lokalu”), także w adresie nieruchomości, a nie tylko w szablonie | generator | **1 K** (#8) | 8.md rozb. 6 |
| G12 | **Podział przedmiotu.** Osoba trzecia ma własną sekcję. Sekcja > ok. 10 pól dzielona po numeracji papieru, > 12 pól → strony (flow-review §5). Pola opisujące całość pod tabelą powtarzalną → zwykła sekcja po niej. Identyczne bloki wariantów (#9 I/II/III) → jedna sekcja | generator + prompt | 3 S + 4 C (#4, #6, #7, #8, #9) | 4.md rozb. 5, 7.md rozb. 6, 9.md rozb. 6, 13, 6.md rozb. 9, 8.md rozb. 17 |
| G13 | **Opis pola nie przeczy konfiguracji.** „Pole nieobowiązkowe…” przy REQ, warunek w opisie bez SHOW → bramka. Pole oznaczone `**` / „opcjonalnie” zostaje jako pole opcjonalne, nie znika. Opis nie parafrazuje etykiety. Dookreślenie w nawiasie („(pełnoletnia)”) → `description` | bramka (regex) + prompt | 3 S + 1 C (#1, #4, #7) | 7.md rozb. 4–5, 4.md rozb. 4, 1.md rozb. 1 |
| G14 | **Gałąź „Czy masz numer PESEL?” tylko dla osób wpisywanych ręcznie**, nigdy w „Twoje dane” z prefillem | szablon | 1 S (#8) | 8.md rozb. 13 |
| G15 | **Lista > 15 opcji → SELECT z `searchEnabled`**, także przy wyborze wielokrotnym (Standardy pkt 4f) | generator | 1 S (#9, od EVAL-1) | 9.md rozb. 8 |
| G16 | **Etykieta pola przedmiotu ≠ etykieta pola szablonu** (np. „Nazwa organu”) → pełna etykieta z papieru | bramka | 1 S (#2) | 2.md rozb. 4 |
| G17 | **Raport.** G7 szuka etykiety w całym tekście strony, gdy G3 znalazł 0 znaczników (pola w ramkach docx). Niespójność źródła (tytuł kontra treść, adresat kontra administrator RODO, S17) → `warnings` | bramka + parser | Fałszywe needs_review i dodatkowe rundy: #2 ($0.017, 51 s), #4 ($0.009, 45 s). Brak ostrzeżeń w #6 i #7 | 2.md (raport), 4.md (raport), 6.md rozb. 7, 7.md rozb. 11 |

G1–G11 pokrywają wszystkie 22 rozbieżności krytyczne wersji edytowalnych. Kolejność: najpierw liczba K, potem S. G5 i G9–G11 to zmiany deterministyczne w generatorze (najtańsze). G1–G4 i G6–G8 wymagają promptu i bramki.

### Do decyzji (nie reguła, tylko konflikt źródeł)
- **PESEL w „Dane innej osoby”.** Standardy s. 15 wymagają pola „Numer PESEL”. Wzorce #1 i #5 go nie mają, a ADR 0023 każe trzymać się wzorców. Papier #3 i #5 identyfikuje wnioskodawcę PESEL-em. Rozbieżność jest liczona jako średnia w 3.md i 5.md.
- **Kto potwierdza oświadczenia osoby trzeciej** (#4 osoba odpowiedzialna, #9 kandydat lub rodzic). Na papierze podpisuje ta osoba, w e-formularzu klika zalogowany: zob. „Pytania” w 4.md i 9.md.

## Co nie wymaga zmian
Szablon strony „Dane” i „Kontakt i zgody” zgodny ze wzorcami. Adresaci urząd/organ zgodni z S1/S1b. #7 bez pełnomocnika: tylko Swoim / Innej osoby (S2). Sekcja powtarzalna psów z poprawnym `$repeatingSectionIndex`. Słowniki proponowane tylko w raporcie (ADR 0025). Szczegóły w sekcjach „Co jest dobrze” w plikach formularzy.
