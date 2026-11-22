# EVAL-5: pomiar końcowy (HEAD 718fa0d)

Tryb jak w [EVAL-4](../eval-4/README.md), tylko porównanie, bez zmian w kodzie. Stos przebudowany (`docker compose up --build -d`). Każdy z 11 plików przeszedł **3 razy, sekwencyjnie** (bez równoległych żądań, więc czasy są prawdziwe). Ocena dotyczy przebiegu mediany (mediana liczby pól, przy remisie needs_review, potem niższy koszt), który leży w `app/results/`. Punktem wyjścia były pliki `eval-4/<n>.md`: każda rozbieżność dostała status, do tego doszły nowe (M…, MS…). Wszystkie 33 wywołania zwróciły 200 i przeszły `POST /forms/validate` oraz schemat.

## K/S/C: EVAL-3 → EVAL-4 → EVAL-5 (wersje edytowalne, przebieg mediany)

| Formularz | EVAL-3 | EVAL-4 | **EVAL-5** | Zniknęło w EVAL-5 | Nowe w EVAL-5 | Plik |
|---|---|---|---|---|---|---|
| #1 numer porządkowy (wzorzec) | 0/0/1 | 0/0/4 | **0/0/4** | 2 | 0/0/2 | [1.md](1.md) |
| #2 zwrot opłaty skarbowej | 2/3/1 | 0/1/1 | **0/1/2** | 0 | 0/0/1 | [2.md](2.md) |
| #3 zaświadczenie | 0/3/3 | 1/1/4 | **0/1/3** | 2 | 0/0/0 | [3.md](3.md) |
| #4 świetlica | 1/4/5 | 1/2/5 | **2/2/6** | 1 | 1/1/1 | [4.md](4.md) |
| #5 nadpłata podatku (wzorzec) | 0/1/3 | 0/0/2 | **0/0/3** | 0 | 0/0/1 | [5.md](5.md) |
| #6 pas drogowy | 2/5/4 | 1/5/3 | **2/2/3** | 4 | 1/1/0 | [6.md](6.md) |
| #7 psy (doc) | 3/5/3 | 1/4/3 | **1/2/4** | 4 | 1/0/2 | [7.md](7.md) |
| #8 deklaracja odpady | 11/4/5 | 6/2/5 | **5/7/6** | 3 | 2/6/2 | [8.md](8.md) |
| #9 stypendium (docx) | 3/7/6 | 2/6/6 | **2/6/6** | 5 | 1/3/2 | [9.md](9.md) |
| **Razem** | **22/32/31** | **12/21/33** | **12/21/37** | **21** | **6/11/11** | |
| #7 skan jpg (pełny wynik) | 4/6/3 | 1/5/3 | **0/4/3** | 3 | 0/0/1 | [7.md#skan](7.md) |
| #9 skan png (tylko dodatkowe względem docx) | 3/5/1 | 0/2/2 | **0/3/1** | 1 | 0/2/1 | [9.md#skan](9.md) |

**Wniosek.** Od EVAL-3 liczba krytycznych spadła z 22 do 12, ale między EVAL-4 a EVAL-5 suma stoi w miejscu (12/21). Zniknęło 21 rozbieżności, doszło 6/11/11 nowych.
- **Poprawy:**
  - #3 nie ma już krytycznych.
  - #6: zniknęły etykiety „Zam”, zdublowane pola i podwójny harmonogram.
  - #7 docx ma opłatę 82 zł w 3/3 przebiegach.
  - #9 odzyskał blok korespondencji (zostało tylko pole „Inny adres”).
  - #8: D.2 ma SHOW, a „Inne załączniki” są opcjonalne.
  - Skan #7 nie ma już krytycznych.
- **Regresy:**
  - #8 w medianie gubi całą sekcję C (okoliczności) i sekcję współmałżonka. Ma je tylko r3, sprawdzone w JSON-ach.
  - #9: pliki oświadczeń z Q34 (11 uploaderów) mają pomieszane warunki.
  - #4 pokazuje oświadczenia wnioskodawcy tylko w gałęzi „inna osoba”.
  - #6 wymaga oświadczenia osoby odpowiedzialnej, którego papier nie przewiduje (tylko r3).
  - #7 w medianie nie ma pola na kopię szczepienia (tylko r2).

## Czasy (sekwencyjnie, jeden kontener)

| Plik | r1 / r2 / r3 [s] | Mediana [s] | Max [s] | Cel |
|---|---|---|---|---|
| #1 | 4.0 / 10.0 / 13.8 | 10.0 | 13.8 | |
| #2 | 29.7 / 13.6 / 35.5 | 29.7 | 35.5 | |
| #3 | 16.1 / 10.8 / 24.1 | 16.1 | 24.1 | |
| #4 | 6.7 / 28.6 / 17.4 | 17.4 | 28.6 | |
| #5 | 14.5 / 30.3 / 26.5 | 26.5 | 30.3 | |
| #6 | 48.7 / 94.5 / 72.2 | 72.2 | 94.5 | |
| #7 doc | 88.3 / 16.4 / 29.5 | 29.5 | 88.3 | |
| **#8** | 33.0 / 42.8 / **98.1** | **42.8** | 98.1 | < 60 s: **2 z 3** (r3 zrobił 4 rundy i większy model) |
| **#9** | 36.7 / 43.2 / 39.7 | **39.7** | 43.2 | < 60 s: **3 z 3** |
| #7 skan | 67.3 / 92.7 / 100.5 | 92.7 | 100.5 | |
| #9 skan | 73.9 / 98.6 / 107.4 | 98.6 | 107.4 | |

#8 i #9 przyspieszyły kilkukrotnie: w EVAL-4 trwały 215–245 s i 178–196 s, ale tamte czasy mierzono przy 3 przebiegach równoległych, więc były zawyżone. Cel < 60 s spełnia #9 w każdym przebiegu, a #8 w 2 z 3. Ogon czasu daje drabina eskalacji: kiedy bramka odrzuca wynik, przebieg robi 4 rundy, ostatnie na modelu large. Tak samo jest w #6 (do 94 s) i #7 docx (88 s w r1).

## Koszty Eden

| Pomiar | Komplet 11 plików | Wszystkie przebiegi |
|---|---|---|
| EVAL-3 (1 przebieg) | $0.2467 | $0.2467 |
| EVAL-4 (3 przebiegi) | mediana $0.2724 | $0.7786 |
| **EVAL-5 (3 przebiegi)** | mediana **$0.2660**, średnio $0.269 | **$0.8071** |

Najdroższe są #8 i #9 (po ok. $0.065–0.077 za przebieg) oraz skan #9 ($0.060–0.072). Razem dają ok. 75% kosztu kompletu.

## Zmienność

Pełne dane: [zmiennosc.md](zmiennosc.md). Bramka przeszła w 3/3 przebiegach tylko w #1. W #6, #8 i obu skanach nie przeszła ani razu. W #2, #3, #4, #5, #7 i #9 wynik bywa różny.

| Plik | Pola r1/r2/r3 | needs_review | Rozbieżności tylko w części przebiegów (z ocen) |
|---|---|---|---|
| #1 | 54/54/54 | 0/0/0 | r3: tytuł bez przedmiotu, „nieruchomość” zamiast „budynek”. Najlepszy jest r2 |
| #2 | 57/54/57 | 3/0/3 | r2 gubi cały pkt 3 (data, kwota, organ), a bramka go przepuszcza: naprawa „strony bez pól” usunęła stronę |
| #3 | 38/38/38 | 1/0/2 | r2: „Cel zaświadczenia” ze SHOW „Inne” (krytyczne tylko tam). r3: fałszywy alarm G3 |
| #4 | 44/43/44 | 2/5/1 | Żaden przebieg nie ma całej gałęzi osoby odpowiedzialnej poprawnie. Upload bez SHOW tylko w r3 (mediana) |
| #5 | 58/58/58 | 2/4/4 | Fałszywy alarm G7 na „(rodzaj podatku)” w r2, r3 (bramka nie przechodzi) |
| #6 | 81/90/85 | 4/10/4 | r2: wraca 12 wymaganych pól NUMBER dla 4 kategorii naraz (krytyczna z EVAL-3). r3: wymagane oświadczenie osoby odpowiedzialnej |
| #7 | 54/53/53 | 6/6/5 | Wybór hodowanie/utrzymywanie poprawny tylko w r2. Brak pliku kopii szczepienia tylko w r2 (mediana) |
| #8 | 93/93/118 | 6/6/18 | Tylko r3 ma sekcję C i pełnego współmałżonka, ale wymaga od każdego oświadczenia o kompostowniku |
| #9 | 100/102/96 | 12/10/7 | r2: brak opinii klubu dla I/II |
| #7 skan | 54/53/54 | 4/6/8 | G28 wykrywa iloczyn opcji, ale naprawa go nie usuwa (3/3) |
| #9 skan | 116/99/96 | 33/13/11 | r1: ok. 20 zmyślonych pól REQ. r1, r3: brak zaświadczeń PZS i bloku korespondencji |

**Ograniczenie metody:** mediana liczby pól nie zawsze jest medianą jakości. W #8 przebiegi r1 i r2 (po 93 pola) gubią dwie sekcje papieru, które ma r3 (118 pól). Około połowa krytycznych z mediany nie występuje we wszystkich przebiegach (#4 N1, #6 M1, #7 M1, #8 M1 i rozb. 2). Z drugiej strony inne przebiegi mają własne krytyczne, których nie ma w medianie (#2 r2, #3 r2, #6 r2, #8 r3). **Głównym problemem jest dziś stabilność, a nie brak reguł.**

## Pozostałe reguły ogólne, posortowane po zysku

K = krytyczne w medianie, „niest.” = krytyczne tylko w innych przebiegach. Numery R odnoszą się do [EVAL-4](../eval-4/README.md).

| # | Reguła (sygnał w treści → wynik) | Gdzie | Zysk | Dowody |
|---|---|---|---|---|
| T1 | **Pliki oświadczeń osób trzecich (Q34) budowane deterministycznie:** jeden plik na blok podpisu osoby trzeciej, w sekcji tej osoby, z warunkiem gałęzi (wariant ∧ wiek ∧ „inna osoba”). Plik powstaje tylko wtedy, gdy papier ma podpis albo „oświadczam” tej osoby. Zgody wnioskodawcy nigdy nie dostają SHOW gałęzi osoby trzeciej | generator | **4 K** (#4 ×2, #6, #9) | 4.md N1, M1; 6.md M1; 9.md M1 |
| T2 | **R1 dokończyć: warunek z treści → SHOW w generatorze, nie w modelu.** „Wypełnić tylko w przypadku…”, „jeżeli TAK w poz. X”, „W PRZYPADKU…” wskazują pole-warunek po numerze pozycji. Bez takiego pola: pole opcjonalne | generator | **3 K** (#8: E.1/E.2 wbrew Q37, zał. A, zwolnienie dochodowe) | 8.md rozb. 3, 7, M2 |
| T3 | **Bramka pokrycia sekcji papieru.** Każdy nagłówek lub sekcja papieru (A, B.2, C, pkt 3…) ma co najmniej jedno pole albo jest jawnie odrzucona jako szablon. Naprawa nie może usuwać strony ani pól. Wynik z mniejszą liczbą pól przedmiotu niż poprzednia runda przechodzi ponowne sprawdzenie pokrycia | bramka | **2 K** + niest. (#8 sekcja C i współmałżonek; #2 r2 pkt 3; #9 r2 opinia) | 8.md rozb. 2, M1; 2.md; 9.md |
| T4 | **Pytanie sterujące stoi w sekcji osoby, po wyborze wariantu, z SHOW wariantu** (np. „Czy kandydat jest pełnoletni?”). Pytanie, od którego nic nie zależy, znika (R2) | generator | **1 K** (#9) | 9.md N2 |
| T5 | **„w załączeniu X” w oświadczeniu daje zgodę i FILE_UPLOADER X naraz** (w sekcji powtarzalnej, gdy „dla każdego”). G24 nie odrzuca wyniku, w którym jest plik, a nie ma oświadczenia | generator + bramka | **1 K** (#7 r2) | 7.md M1 |
| T6 | **R8 deduplikacja po etykiecie bez znaczników pozycji** („(pierwszy/drugi wiersz)”, „_2”). Wiersze tabeli (przedziały m², kategorie) nie są duplikatami. Jedna pozycja papieru daje jedno pole | generator | **1 K** + 1 S (#6, #8) | 6.md rozb. 3, 8.md M3–M5 |
| T7 | **Bramka bez fałszywych alarmów** (R10 dokończyć): G7 traktuje podpis pod linią („(rodzaj podatku)”) i etykietę z nagłówka tabeli jako etykietę pola. G11 pomija bloki szablonu, datę i podpis. G3 przyjmuje pole „Inne” ze SHOW jako pokrycie „inne ___”. needs_review z kotwicą bloku cytuje jego tekst | bramka | Stabilność i koszt: ogon czasu #6, #7, #8; bramka nie przechodzi w #2, #3, #5 przez fałszywe alarmy | 2.md, 3.md, 5.md M1 |
| T8 | **G12: przy scalaniu sekcji warunki z różnych radiów sterujących się sumują** (sportowiec ∨ trener), a nie zostaje tylko pierwsze | generator | 1 S (#9) | 9.md M4 |
| T9 | **Iloczyn opcji (G28) rozbija na osobne RADIO generator,** bez kolejnej rundy modelu | generator | 1 S (#7, skan 3/3) | 7.md |
| T10 | **Ostrzeżenia Q35/Q36 tylko przy wykrytej sprzeczności i zawsze wtedy.** Dziś #1 ma fałszywe ostrzeżenie, a #7 (charty) i #9 (adresat) nie mają ostrzeżenia w 6/6 i 3/3 przebiegach | prompt + filtr raportu | raport (#1, #7, #9) | 1.md N3, 7.md rozb. 11, 9.md M6 |
| T11 | **„Wskaż rodzaje…”, lista kratek bez „zaznacz jedną” → CHECKBOX.** Opcje w mianowniku | prompt | 1 S + 1 C (#9, #3) | 9.md M2, 3.md |
| T12 | **Etykieta i opis:** opis nie parafrazuje etykiety. Przedmiot wniosku i tytuł brane z „wnoszę o…”. Rachunek z walidatorem Pattern `^\d{26}$` | prompt + generator | kilka C (#1, #2) | 1.md, 2.md |

T1–T6 obejmują wszystkie 12 krytycznych z mediany i większość krytycznych z pozostałych przebiegów. T1, T2, T4, T6, T8 i T9 to zmiany deterministyczne w generatorze. Po nich model wpływa na wynik mniej, więc powinna spaść i liczba błędów, i zmienność.

## Ograniczenia
- Oceny powstały z konspektów JSON i tekstu z pdftotext, bez oglądania obrazów skanów. Sam sprawdziłem w JSON-ach tylko rozbieżności #8 (brak sekcji C i współmałżonka w r1/r2, obecne w r3).
- Po każdym EVAL wagi przypisywali agenci według tej samej skali, ale część ocen granicznych (średnia czy krytyczna) może się różnić między pomiarami.
- Stos zatrzymany `docker compose down` (bez `-v`).
