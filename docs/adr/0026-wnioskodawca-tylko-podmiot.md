# 0026. Wnioskodawca „tylko podmiot”: bez pola „w czyim imieniu”, odpis z rejestru według dokumentu, dowód pełnomocnika
Data: 2026-11-21 · Status: przyjęta · Zastępuje: Q20 i Q31 z `app/docs/design/generator.md`
Źródło: UŻYTKOWNIK, na podstawie `research/2026-11-21-wnioskodawca-podmiot.md`

## Kontekst
- Q20 dawała w wariancie ENTITY (#9) CHECKBOX z jedną opcją „jak na papierze”, a Q31 robiła go wymaganym. Jako opcjonalny pozwalał ukryć dane wnioskodawcy, jako wymagany zmuszał do kliknięcia czegoś, co nic nie zmienia.
- Standardy s.10: „Jeśli formularz przewiduje wyłącznie dane firmy lub instytucji, należy umożliwić podanie danych podmiotu”. Bez słowa o wyborze. Standardy s.5 pkt 4d–4e: radio i checkbox służą do wyboru z listy, a jedna opcja to nie lista.
- Papier #9 s.2 wymaga odpisu z KRS od każdego klubu, a wzorce #1 i #5 tylko od reprezentanta.
- Papier #9 s.2 pyta pełnomocnika o serię i numer dowodu osobistego.

## Decyzja
1. W wariancie ENTITY nie ma pola „Wybierz, w czyim imieniu wnioskujesz” ani przełącznika `entity_required`. „Dane podmiotu” i „Adres siedziby” są widoczne zawsze, a radio „Wybierz, jako kto wnioskujesz” (Pełnomocnik / Reprezentant) jest wymagane i bez warunku. Realizuje to ogólna reguła generatora: pole wyboru z jedną opcją znika, a warunek na tej opcji jest zawsze spełniony. REGON w „Dane podmiotu” jest wymagany (Standardy s.17).
2. Seria i numer dowodu osobistego pełnomocnika to pole w sekcji „Pełnomocnictwo”, gdy dokument o nie pyta. Według ADR 0022 byłoby daną inicjalną, ale żaden rejestr z „Danych inicjalnych” nie ma takiego atrybutu, więc pole jest edytowalne, z walidatorem `SERIAL_NUMBER_ID_CARD`.
3. Odpis z rejestru: ekstrakcja ustawia w FieldTree `entity_extract_required`, gdy dokument wymaga odpisu od każdego podmiotu-wnioskodawcy. Wtedy upload odpisu jest wymagany przy każdym podmiocie, także przy pełnomocniku. Bez sygnału odpis jest tylko od reprezentanta, jak we wzorcach.

## Konsekwencje
- Wariant ENTITY nie ma pustego kliknięcia i nie da się w nim ukryć danych wnioskodawcy.
- Ta sama reguła „jedna opcja znika” obejmuje każdy inny przypadek, w którym po wyborze wariantu zostaje jedna opcja.
- Do czasu, aż ekstrakcja doda `entity_extract_required` do FieldTree, generator przyjmuje `false`, więc wynik dla #1 i #5 się nie zmienia.
