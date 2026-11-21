# 0024. Reguły, prompty i bramki są uniwersalne, bez poprawek pod konkretny formularz
Data: 2026-11-21 · Status: przyjęta
Źródło: ZESPÓŁ

## Kontekst
- Na #7 mistral-small odpada na bramce (G5: oświadczenia jako checkbox z jedną opcją, G4: zła nazwa opcji w `show_if`). Drabinka eskaluje na mistral-large i wynik jest poprawny, ale kosztuje 2 dodatkowe wywołania.
- Kuszące jest dopisanie do promptu albo bramki reguły, która „naprawia #7”. Takie poprawki dopasowują rozwiązanie do 9 formularzy z materiałów, a jury sprawdza też formularze, których nie widzieliśmy.

## Decyzja
- Prompty, bramki (G*, M*) i reguły generatora opisują ogólne cechy dokumentów i JSON COI, a nie konkretne formularze. Nie ma w nich nazw, fraz ani wyjątków z #1–#9.
- Gdy model odpada na formularzu, nie „łatamy” go. Drabinka eskalacji jest mechanizmem na takie przypadki. Regułę zmieniamy tylko wtedy, gdy błąd jest ogólny (np. ten sam problem na kilku formularzach albo sprzeczność z wzorcami #1 i #5).
- Formularze z materiałów są zestawem testowym i regresyjnym, nie specyfikacją do przepisania w kodzie.

## Konsekwencje
- Część formularzy przechodzi dopiero na droższym szczeblu (wyższy koszt i czas na #7), co akceptujemy.
- Każda zmiana promptu albo bramki wymaga uzasadnienia ogólnego, a nie „bo #N nie przechodził”. W przeglądzie kodu szukamy nazw i fraz z konkretnych formularzy.
