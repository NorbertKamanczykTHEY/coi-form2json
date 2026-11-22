# EVAL-4: ponowny pomiar po poprawkach z EVAL-3 (HEAD af98b50)

Ten sam tryb co [EVAL-3](../eval-3/README.md): najpierw interpretacja papieru według materiałów COI, potem porównanie z JSON-em. W kodzie nic nie zmieniono. Różnice względem EVAL-3:
- Każdy z 11 plików (#1–#9 edytowalne, skany #7 jpg i #9 png) przeszedł przez aplikację **3 razy** (docker compose, obraz z af98b50, 3 przebiegi równolegle). Ocena dotyczy **przebiegu mediany** (mediana liczby pól, przy remisie needs_review, potem niższy koszt). Ten przebieg leży w `app/results/`. Zmienność opisuje sekcja niżej i plik [zmiennosc.md](zmiennosc.md).
- Punktem wyjścia były pliki `eval-3/<n>.md`. Każda stara rozbieżność dostała status (zniknęła, częściowo, została), do tego doszły nowe i regresy.
- Uwzględnione decyzje: **Q33** (PESEL w „Dane innej osoby”), **Q34** (oświadczenie osoby trzeciej jako plik), **Q35** (adresat z nagłówka + warning), **Q36** (treść niespójna z tytułem zostaje + warning), **Q37** (E.1/E.2 wymagane tylko w swojej gałęzi), **G15** (wybór wielokrotny zostaje CHECKBOX-em).

Wszystkie 33 wywołania zwróciły 200 i przeszły `POST /forms/validate` oraz schemat. **Koszt Eden:** przebiegi mediany $0.2724, wszystkie 3 przebiegi $0.7786.

## Przed i po (wersje edytowalne, przebieg mediany)

| Formularz | EVAL-3 K/S/C | **EVAL-4 K/S/C** | Zniknęło (w tym decyzją) | Nowe K/S/C | Plik |
|---|---|---|---|---|---|
| #1 numer porządkowy (wzorzec) | 0/0/1 | **0/0/4** | 0 | 0/0/3 | [1.md](1.md) |
| #2 zwrot opłaty skarbowej | 2/3/1 | **0/1/1** | 5 (0) | 0/0/1 | [2.md](2.md) |
| #3 zaświadczenie | 0/3/3 | **1/1/4** | 2 (1: Q33) | 1/0/1 | [3.md](3.md) |
| #4 świetlica | 1/4/5 | **1/2/5** | 4 (0) | 1/1/0 | [4.md](4.md) |
| #5 nadpłata podatku (wzorzec) | 0/1/3 | **0/0/2** | 2 (1: Q33) | 0/0/0 | [5.md](5.md) |
| #6 pas drogowy | 2/5/4 | **1/5/3** | 5 (1: Q35) | 0/2/1 | [6.md](6.md) |
| #7 psy (doc) | 3/5/3 | **1/4/3** | 6 (0) | 0/1/2 | [7.md](7.md) |
| #8 deklaracja odpady | 11/4/5 | **6/2/5** | 11 (1: G15) | 1/2/1 | [8.md](8.md) |
| #9 stypendium (docx) | 3/7/6 | **2/6/6** | 7 (3: G15, Q34 ×2) | 2/4/0 | [9.md](9.md) |
| **Razem** | **22/32/31** | **12/21/33** | **42 (7)** | **5/10/9** | |
| #7 skan jpg (pełny wynik skanu) | 4/6/3 | **1/5/3** | 7 (0) | 0/1/2 | [7.md#skan](7.md) |
| #9 skan png (tylko dodatkowe względem docx) | 3/5/1 | **0/2/2** | 6 (1: Q34) | 0/0/2 | [9.md#skan](9.md) |

Liczba rozbieżności krytycznych spadła z 22 do 12, a średnich z 32 do 21. Kosmetycznych przybyło (31 → 33), głównie przez etykiety: znacznik przypisu, przyimek, „Zam”, „PESEL” na kilku polach. Poprawki działają w #2 (0 krytycznych, needs_review 10 → 0), #8 (11 → 6 krytycznych) i w skanie #7 (oświadczenia wróciły do CONSENT_SECTION, jest opłata 82 zł). Regresy: #9 zgubił blok korespondencji klubu (krytyczny we wszystkich 3 przebiegach), a #3 i #4 dostały wymagane uploady bez podstawy lub bez warunku.

## Zmienność 3 przebiegów

| Formularz | Pola r1/r2/r3 | needs_review | Bramka (przeszła, rundy) | Koszt r1/r2/r3 [$] | Rozbieżności tylko w części przebiegów |
|---|---|---|---|---|---|
| #1 | 54/54/54 | 0/0/0 | tak(1) ×3 | 0.0018/0.0012/0.0006 | Opisy-parafrazy i etykieta „Przy ulicy1)” w r2, r3; r1 bez opisów, za to etykieta „Nazwa ulicy” |
| #2 | 57/57/57 | 0/0/0 | tak(3)/tak(4)/tak(4) | 0.0129/0.0120/0.0116 | Brak: trzy przebiegi dały identyczny wynik |
| #3 | 39/39/39 | 0/0/0 | tak(1) ×3 | 0.0018/0.0005/0.0005 | r3: lista „Proszę o…” jako RADIO zamiast CHECKBOX; tytuł poprawny tylko w r3 |
| #4 | 42/41/42 | 6/5/6 | NIE(4) ×3 | 0.0084/0.0073/0.0083 | Gałąź osoby odpowiedzialnej za każdym razem inna: r1 ma odwrócony SHOW, r2 nie ma gałęzi, r3 nie ma SHOW przy uploadzie. Informacja o pełnoletności tylko w r1, r2 |
| #5 | 58/58/58 | 2/2/2 | tak(3)/tak(4)/tak(4) | 0.0075/0.0070/0.0079 | r3: „Uzasadnienie” bez osobnej sekcji |
| #6 | 85/86/77 | 11/11/10 | NIE ×3 | 0.0192/0.0188/0.0188 | r3: adres osoby odpowiedzialnej to samo pole „Miejscowość” (stąd 77 pól). r2: cały przedmiot na jednej stronie, pole-śmieć „Mui”, zdublowane pola drogi |
| #7 | 53/52/52 | 5/5/5 | tak(4)/tak(3)/tak(3) | 0.0120/0.0069/0.0095 | Zgoda „Zaszczepiono…” tylko w r1. Etykieta daty bez „przeciwko wściekliźnie” tylko w r3 |
| #8 | 110/113/117 | 27/25/26 | NIE(4) ×3 | 0.0628/0.0752/0.0623 | r1 gubi „Składający deklarację”, więc sekcja współmałżonka nie ma SHOW (krytyczne). r3 dubluje blok wnioskodawcy i wymaga NIP/REGON od osoby fizycznej (krytyczne). D.2 ma SHOW tylko w r1 |
| #9 | 77/76/73 | 22/18/21 | NIE ×3 | 0.0537/0.0610/0.0521 | N5 (dyscypliny także przy nagrodzie) tylko w medianie. r1: brak opinii klubu dla I/II. r3: brak opinii dla III |
| #7 skan | 45/49/63 | 5/6/6 | tak/tak/NIE(4) | 0.0136/0.0104/0.0190 | r2, r3: brak wyboru hodowanie/utrzymywanie. r3: metryka i rodowód wymagane (papier: `**` opcjonalne), presety adresu poprzedniego właściciela i miejsca |
| #9 skan | 75/82/68 | 20/23/16 | NIE(4) ×3 | 0.0678/0.0724/0.0542 | r2: scalanie wariantów nie zadziałało. r3: brak danych kandydata i trenera, korespondencja poprawna |

Wnioski:
- **Krótkie formularze są stabilne** (#1, #2, #3, #5: ta sama liczba pól, bramka przechodzi za każdym razem).
- **Bramka nie przechodzi w żadnym przebiegu #4, #6, #8, #9 ani skanu #9.** W każdym z nich zużywa 3–4 rundy, w tym na model large, i daje losowy wynik ostatniej rundy. Agenci wskazują przyczynę w fałszywych alarmach G7 (pola po poprawnej konwersji typu, etykiety w opcjach i nagłówkach tabel, pliki tworzone przez Q34) oraz „warunek bez SHOW” na samym pytaniu Tak/Nie (reguła R10 niżej). Usunięcie tych alarmów obniży koszt, a przede wszystkim zmienność.
- Rozbieżności krytyczne w medianie są stabilne (3/3) w #3, #7, #8 (E.1/E.2, D.2, A/B) i #9 (N1). Niestabilne są #4 N1 i dodatkowe krytyczne #8 z r1 i r3.

## Reguły ogólne po EVAL-4, posortowane po zysku

Zysk liczony jako rozbieżności w przebiegu mediany (K = krytyczne, S = średnie, C = kosmetyczne). R1–R9 obejmują wszystkie 12 krytycznych, które zostały. Numery G odwołują się do [reguł z EVAL-3](../eval-3/README.md), wdrożonych w af98b50.

| # | Reguła (sygnał w treści → wynik) | Gdzie wdrożyć | Zysk | Dowody |
|---|---|---|---|---|
| R1 | **G1 dokończyć: warunek z treści pola staje się SHOW.** Pole lub sekcja, w których źródle albo `description` jest „Wypełnić tylko w przypadku…”, „W PRZYPADKU…”, „jeśli … w poz. X”, dostaje SHOW na polu, które ten warunek wskazuje. Bez takiego pola: pole opcjonalne. Dziś warunek zostaje tylko w opisie, a pole jest REQ | generator (deterministycznie, z `description` i numeracji) + bramka | **3 K** (#8 E.1/E.2 wbrew Q37, D.2, załączniki A/B) | 8.md rozb. 3, 5, 7 |
| R2 | **Pola i pliki osoby trzeciej zależą od gałęzi „inna osoba”.** Pytanie sterujące (np. „Kto odpowiada…”, „Czy kandydat jest pełnoletni?”) stoi w sekcji tej osoby, przed polami zależnymi, a nie przed wyborem rodzaju wniosku. Pytanie, od którego nic nie zależy, znika. Bramka sama naprawia brak SHOW, a nie tylko zgłasza go w needs_review | generator + bramka | **2 K** (#4, #9) | 4.md N1, 9.md N2 |
| R3 | **Pominięcie sekcji „adres wnioskodawcy jest w szablonie” usuwa tylko pola adresu.** Wybór kanału (poczta / ePUAP / e-Doręczenia), skrzynka ePUAP (`EPUAP`) i adres ADE (`ADE`) zostają w przedmiocie | generator | **1 K**, regres (#9 we wszystkich 3 przebiegach) | 9.md N1 |
| R4 | **Adres osoby w przedmiocie to preset adresu z etykietami szablonu** (Kraj, Miejscowość, Kod pocztowy…). Etykieta z papieru („zam.”, „Adres miejsca utrzymywania”) staje się tytułem sekcji. Preset tylko wtedy, gdy papier pyta o adres. Adres miejsca, który dotyczy całego wniosku, nie trafia do sekcji powtarzalnej | generator + prompt | **1 K** + 3 S (#6, #7, #8, #9) | 8.md rozb. 2, 6.md (etykiety „Zam”), 7.md N1, 9.md N3 |
| R5 | **Etykiety gałęzi „brak PESEL” zawsze z szablonu** („Rodzaj dokumentu”, „Numer dokumentu”), nigdy z pola źródłowego („PESEL”) | generator | **1 K** (#8) | 8.md N1 |
| R6 | **Upload potwierdzenia zapłaty tylko wtedy, gdy papier każe je dołączyć.** Gdy papier mówi „zapłać przed złożeniem” albo wspomina zwolnienie, zostaje sama informacja o opłacie (TEXT_BLOCK) albo upload opcjonalny | prompt ekstrakcji (`case_fee_proof`) + G8 | **1 K** (#3) | 3.md N1 |
| R7 | **G8 w dokumentach edytowalnych: kwota w zł z numerem konta → sekcja „Opłata”.** Bramka zgłasza dokument, w którym jest kwota z kontem, a nie ma bloku opłaty (#7 docx: 0/3 przebiegów, skan: 3/3) | bramka + prompt | **1 K** (#7) | 7.md rozb. 3 |
| R8 | **Jedno miejsce do wpisania to jedno pole.** W wierszu sekcji powtarzalnej nie ma dwóch pól o tej samej etykiecie („druga pozycja”, „_2”). Dwa opisy przy jednym miejscu to jedno pole. Ten sam dokument nie trafia do dwóch uploaderów | generator (deduplikacja etykiet w sekcji) + prompt | **1 K** + 2 S (#6) | 6.md rozb. 3, 5, N („Cel zajęcia”) |
| R9 | **G3 w generatorze: „Inne (podać jakie)” na liście załączników → opcjonalny FILE_UPLOADER**, bez względu na wynik ekstrakcji | generator | **1 K** (#8) | 8.md rozb. 9 |
| R10 | **Bramka bez fałszywych alarmów.** G7 nie zgłasza pól po konwersji typu (daty, liczby, preset), etykiet znalezionych w opcjach albo nagłówkach kolumn ani plików z Q34. „Warunek bez SHOW” nie dotyczy samego pola sterującego Tak/Nie. Pliki z Q34 dostają opis: czyje to oświadczenie i co zawiera | bramka + generator | Stabilność i koszt: bramka nie przechodzi 3/3 w #4, #6, #8, #9; needs_review #9 18–22 | 6.md, 8.md, 9.md (raport), zmiennosc.md |
| R11 | **Scalanie wariantów (G12) nie poszerza warunku sekcji, która występuje w jednym wariancie.** Pliki „ten sam dokument” łączą się tylko przy tym samym SHOW | generator | 2 S (#9) | 9.md N4, N5 |
| R12 | **Wybór na kilku osiach → osobne RADIO dla każdej osi** (hodowanie/utrzymywanie, chart/charty, rasowy/mieszaniec), bez iloczynu opcji. Liczba sztuk nie jest opcją, gdy jest sekcja powtarzalna | prompt + bramka | 1 S (#7; skan r2, r3 gubi wybór) | 7.md rozb. 1 |
| R13 | **Osoba fizyczna trzecia: „Imię” i „Nazwisko” osobno; gdy osobą może być firma: jedno pole „Imię i nazwisko lub nazwa”** (godzi #4 z regułą G2) | generator + prompt | 1 S (#4) | 4.md N2, 2.md |
| R14 | **Etykieta czysta:** bez znacznika przypisu („ulicy1)”), wiodącego przyimka („W miejscowości”), skrótu z papieru („Zam”, „Tel”) i numerów pozycji w opisach i zgodach („pozycji 51”). Instrukcja w nawiasie przy tytule punktu zostaje opisem pola | generator (filtr) + prompt | ok. 8 C (#1, #2, #6, #8) | 1.md N1–N3, 2.md N1, 8.md N3 |
| R15 | **Ostrzeżenia Q35/Q36 tylko przy wykrytej niespójności i zawsze wtedy.** #1 ma ostrzeżenie „jest spójny”, a #7 docx nie ma ostrzeżenia o chartach w żadnym przebiegu | prompt + filtr raportu | raport (#1, #7) | 1.md, 7.md |
| R16 | **Lista kratek bez instrukcji „zaznacz jedną” → CHECKBOX** | prompt | stabilność (#3 r3) | 3.md |

### Co działa po poprawkach (nie psuć)
Opcje „Podmiot wniosku” ze Standardów (G5), RADIO Tak/Nie zamiast wymaganego CHECKBOX-a z jedną opcją (G9), pole „Razem” i stawki w opisach (G6), opcjonalny numer lokalu (G11), zgoda na e-mail opcjonalna, jedna zgoda RODO, treść zgód neutralna i w czasie teraźniejszym (G4). Także: sekcja powtarzalna powierzchni w #6, upload kopii szczepienia w #7, dowód osobisty pełnomocnika w #9, PESEL w „Dane innej osoby” (Q33).

## Ograniczenia pomiaru
- Ocenę zrobili agenci na podstawie konspektów JSON i tekstu z pdftotext. Obrazów skanów nie oglądali ponownie.
- Czasy w tabelach pochodzą z 3 przebiegów puszczonych równolegle na jednym kontenerze, więc są zawyżone.
- Obraz backendu zbudowano z drzewa roboczego przy HEAD af98b50. Po przebiegu w drzewie były niezacommitowane zmiany innych wątków w `backend/coi/api.py` i `store.py`. Nie wiadomo, czy trafiły do obrazu; ekstrakcji i generatora i tak nie dotyczą.
