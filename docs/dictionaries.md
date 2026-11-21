# Słowniki: katalog, dane, dopasowanie, API

Kod: `app/backend/coi/dictionaries/` (modele, seed, matcher, blueprint). Dane: `coi/dictionaries/seed/*.json.gz`, budowane raz skryptem `app/backend/scripts/fetch_dictionaries.py`. W runtime nie ma żadnych wywołań sieciowych.

## Katalog

| id (`dictionaryName`) | Pochodzenie | Pozycje | Struktura | Źródło |
|---|---|---|---|---|
| `Kraje` | materiały | 250 | płaska, id = ISO 3166-1 alfa-2 | CLDR (polskie nazwy) |
| `TERYT_4G_DOWODOWY` | materiały | 57 352 | drzewo: województwo → powiat → gmina → miejscowość | GUS TERC + SIMC |
| `WOJEWODZTWO` | materiały | 16 | płaska | GUS TERC |
| `POWIAT` | materiały | 380 | płaska, `parent` = województwo | GUS TERC |
| `GMINA` | materiały | 2 479 | płaska, `parent` = powiat | GUS TERC |
| `MIEJSCOWOSC` | materiały | 54 477 | płaska, `parent` = gmina | GUS SIMC |
| `NUMERY_KIERUNKOWE` | materiały | 243 | płaska, id = ISO, `value` = `+48` | libphonenumber |
| `DYSCYPLINY_SPORTOWE` | katalog (propozycja) | 3 + 20 | drzewo: rodzaj → dyscyplina | wniosek #9 |
| `RASY_PSOW_AGRESYWNYCH` | katalog (propozycja) | 11 | płaska | rozporządzenie MSWiA, Dz.U. 2003 nr 77 poz. 687 |
| `SPOSOBY_DORECZENIA` | katalog (propozycja) | 3 | płaska | wniosek #9 |
| `RODZAJE_PODATKOW_LOKALNYCH` | katalog (propozycja) | 10 | płaska | ustawy podatkowe (niżej) |

Pochodzenie (`origin`):
- `materials`: słownik nazwany w materiałach zadania. Jest chroniony: `DELETE` zwraca 409 `protected_dictionary`. Edycja pozycji jest dozwolona.
- `catalog`: nasza propozycja nowego słownika, przygotowana offline z oficjalnej listy. Dopasowanie do niej daje `decision: "new"` z gotową propozycją (rozszerzenie II).
- `user`: słownik utworzony przez API albo przyjęty z propozycji (`from-proposal`). Kolejne formularze dopasowują go już jako istniejący.

Nazwy `Kraje`, `TERYT_4G_DOWODOWY` i `TERYT_DOWODOWY` pochodzą z wzorców #1 i #5. Pozostałe identyfikatory materiałowe (`WOJEWODZTWO`…`NUMERY_KIERUNKOWE`) są nasze, bo „Słowniki.docx” podaje tylko nazwy opisowe. Do potwierdzenia z mentorami.

### TERYT_4G_DOWODOWY a TERYT_DOWODOWY
**Decyzja użytkownika (2026-11-21):** `TERYT_4G_DOWODOWY` jest słownikiem głównym, a `TERYT_DOWODOWY` jego aliasem. W bazie jest tylko ten pierwszy. Mapa aliasów leży w `coi/config/dictionaries.py` (`config("dictionaries.aliases")`), a `coi.dictionaries.canonical(name)` ją stosuje. Przez alias przechodzą: wynik `match()`, odczyt i edycja w REST API (`GET /dictionaries/TERYT_DOWODOWY` zwraca `TERYT_4G_DOWODOWY`, `POST` z id aliasu daje 409) oraz, po stronie generatora, `dictionaryName` z szablonów. Baza utworzona przed tą zmianą zachowuje stary wiersz `TERYT_DOWODOWY` (seed tylko dopisuje brakujące słowniki), ale API go już nie zwraca pod tą nazwą; czysta baza go nie ma.

Tło: materiały nie definiują różnicy. Wzorce używają obu zamiennie w tym samym miejscu: adres zamieszkania w #1 ma `TERYT_DOWODOWY`, a w #5 `TERYT_4G_DOWODOWY`. W obu przypadkach obok jest pole tekstowe „Ulica”, więc żaden z nich nie schodzi do ulic (ULIC). Nasza interpretacja, oparta na nazwie („4G” = 4 poziomy):
- **TERYT_4G_DOWODOWY**: dokładnie 4 poziomy. Gmina jest jednostką prawną (rodzaj 1 miejska, 2 wiejska, 3 miejsko-wiejska). Miasto i obszar wiejski gminy miejsko-wiejskiej (4, 5) oraz dzielnice Warszawy i delegatury (8, 9) wpadają do swojej gminy. Miejscowości to tylko samodzielne pozycje SIMC (`SYM = SYMPOD`).
- **TERYT_DOWODOWY**: wcześniej budowaliśmy go jako pełny (5. poziom: części miejscowości z SIMC). Po decyzji o aliasie ta wersja wypadła z seeda i z `scripts/fetch_dictionaries.py`.

Identyfikatory pozycji: województwo `10`, powiat `1020`, gmina `102001_1` (TERC `WOJ POW GMI _ RODZ`; podkreślnik jest potrzebny, bo 7-cyfrowy kod TERC koliduje z 7-cyfrowym SYM z SIMC), miejscowość to SYM z SIMC (`0974460`).

Kolejność: alfabetyczna po polsku w obrębie rodzica (ą po a, ł po l). Gmina ma w nazwie rodzaj: „Zgierz (gmina miejska)” i „Zgierz (gmina wiejska)” leżą w jednym powiecie.

## Źródła, daty, licencje

| Zbiór | Źródło | Stan | Licencja i warunki |
|---|---|---|---|
| TERC, SIMC (urzędowe) | GUS, eTERYT: `eteryt.stat.gov.pl` → Pobieranie → Pliki pełne (`TERC_Urzedowy_2026-11-21.zip`, `SIMC_Urzedowy_2026-11-21.zip`) | rejestr na 2026-01-01, pobrane 2026-11-21 | Informacja publiczna, dane rejestru udostępniane nieodpłatnie. Przy ponownym wykorzystaniu podajemy źródło: „GUS, rejestr TERYT” |
| Kraje | Unicode CLDR przez `babel` 2.18.0 (`Locale('pl').territories`) | CLDR z babel 2.18.0 | Unicode License v3 (dane), BSD-3 (babel) |
| Numery kierunkowe | libphonenumber (Google) przez `phonenumbers` 9.0.44 | j.w. | Apache-2.0 |
| Rasy psów | Rozporządzenie MSWiA z 28.04.2003 w sprawie wykazu ras psów uznawanych za agresywne, Dz.U. 2003 nr 77 poz. 687, § 1 (11 ras; akt obowiązuje) | 2003 | Akt normatywny, nie podlega prawu autorskiemu (art. 4 pkt 1 pr. aut.) |
| Dyscypliny, sposoby doręczenia | Wniosek #9 (Zarządzenie Nr 245/IX/2024 Prezydenta Miasta Zgierza, zał. 3) z materiałów zadania | 2024-11-26 | Dokument urzędowy (art. 4 pr. aut.) |
| Podatki i opłaty lokalne | Ustawa z 12.01.1991 o podatkach i opłatach lokalnych, ustawa z 15.11.1984 o podatku rolnym, ustawa z 30.10.2002 o podatku leśnym | stan prawny 2026 | Akty normatywne (art. 4 pr. aut.) |

Pobieranie TERYT: serwis GUS udostępnia pliki tylko przez postback ASP.NET (przycisk „Pobierz”). Skrypt odtwarza ten postback: pobiera stronę, odsyła jej ukryte pola z `__EVENTTARGET`. Lustro nie było potrzebne. Kopie zipów leżą w `scripts/.cache/` (poza gitem), a `seed/sources.json` zapisuje nazwy plików, liczby i wersje bibliotek.

Kontrola liczb (test `test_teryt_counts_match_gus`): 16 województw, 380 powiatów (314 powiatów + 66 miast na prawach powiatu), 2479 gmin (302 miejskie, 1453 wiejskie, 724 miejsko-wiejskie). Zgadza się z GUS („Polska w liczbach 2026”) i z bazą JST MSWiA na 1.01.2026. Wszystkie 101 865 wierszy SIMC trafiają do drzewa (54 477 miejscowości + 47 388 części).

Kraje: 250 kodów, czyli 249 z ISO 3166-1 i Kosowo (`XK`). Odrzucamy grupy i kody wyjątkowo zastrzeżone, które CLDR też zwraca (`EU`, `UN`, `AC`, `IC`…). Numery kierunkowe: 243, bo kilka terytoriów nie ma własnego prefiksu (np. Antarktyda, Wyspa Bouveta).

Nie robiliśmy krajowych numerów kierunkowych (strefy numeracyjne). „Słowniki.docx” definiuje ten słownik jako międzynarodowe prefiksy krajów, a w Polsce od 2005 r. numer stacjonarny ma 9 cyfr razem ze strefą, więc osobny wybór strefy nic nie daje.

Odświeżenie danych: `cd app/backend && rm -rf scripts/.cache && uv run python scripts/fetch_dictionaries.py`. Seed dokłada do bazy tylko słowniki, których w niej nie ma, więc nie nadpisuje edycji. Pełne przeładowanie wymaga usunięcia słownika albo bazy.

## Tabele (SQLAlchemy, na wspólnym `Base` z `coi.store`)

`dictionaries`: `id` (PK = `dictionaryName`), `name`, `description`, `origin`, `levels` (JSON: nazwy poziomów; >1 oznacza `multiLevelTree`), `aliases` (JSON: etykiety pól dla matchera), `created_by/at`, `updated_by/at`.

`dictionary_items`: PK (`dictionary_id`, `id`), `parent` (id rodzica w tym samym słowniku), `name`, `value` (wartość, gdy różni się od nazwy, np. `+48`), `level`, `pos` (kolejność), `norm` (nazwa bez wielkich liter i znaków diakrytycznych, do wyszukiwania i porównań). Indeksy: (`dictionary_id`, `parent`, `pos`) dla drzewa i `norm` dla dopasowania opcji.

Seed przy starcie (`init_app` w `create_app`): każdy słownik idzie w osobnej transakcji. Na pustej bazie SQLite trwa około 1,6 s i daje plik ~34 MB. Dwa workery gunicorna startujące równocześnie nie wywołają błędu, bo `IntegrityError` drugiego jest pomijany. Działa na każdej bazie z `DATABASE_URL`, ponieważ wyszukiwanie to zwykły `LIKE` po kolumnie `norm`.

## API (`/api/v1/dictionaries`, JWT, błędy RFC 9457)

| Metoda i ścieżka | Co robi | Kody |
|---|---|---|
| `GET /dictionaries` | katalog: metadane, `protected`, liczba pozycji | 200, 401 |
| `GET /dictionaries/{id}?parent=&q=&limit=&offset=` | strona pozycji. Bez `q`: dzieci `parent` (bez niego: korzeń). Z `q`: trafienia w całym drzewie, najkrótsze pierwsze, każde z `path` (nazwy przodków). `limit` ≤ 500 | 200, 400, 404 |
| `POST /dictionaries` | nowy słownik `{id, name, description, levels, aliases, items[{id, name, parent, value}]}` | 201, 400, 409 |
| `PUT /dictionaries/{id}` | zmiana podanych pól, `items` zastępuje wszystkie | 200, 404, 409 |
| `DELETE /dictionaries/{id}` | usunięcie słownika z pozycjami. Słowniki z materiałów: 409 `protected_dictionary` | 204, 404, 409 |
| `POST /dictionaries/{id}/items` | dodanie pozycji (`level` z rodzica) | 201, 404, 409 |
| `PUT /dictionaries/{id}/items/{itemId}` | zmiana nazwy, rodzica, wartości | 200, 404, 409 |
| `DELETE /dictionaries/{id}/items/{itemId}` | usunięcie pozycji bez dzieci | 204, 404, 409 |
| `POST /dictionaries/match` | `{label, source_label, type, options}` → `{match: DictMatch \| null}` | 200, 400 |
| `POST /dictionaries/from-proposal` | przyjęcie wpisu z `report.proposed_dictionaries` | 201, 409 |

## Dopasowanie pola (`coi.dictionaries.match`)

```python
with store.session() as s:
    m = match(s, label, source_label, type, options)   # None albo DictMatch
```
`DictMatch = {dictionaryName, decision: existing|new, score, reason, component: SELECT|RADIO|CHECKBOX, multiLevelTree, searchEnabled, proposal}`. `proposal` jest `None`, gdy słownik istnieje. W przeciwnym razie ma postać `{id, name, description, levels, items: [{id?, name, children?}], source: catalog|document}`. Generator dopisuje `fields: [techName…]` i wstawia ją do `report.proposed_dictionaries`. `from-proposal` przyjmuje dokładnie ten obiekt.

Reguły (kolejność jak w flow-review, § 4):
1. **Istniejący słownik.** Etykieta (bez nawiasów i wielokropków, bez znaków diakrytycznych) jest porównywana z nazwą i aliasami każdego słownika w bazie. Wynik 1,0 oznacza równość. Literówki ocenia `rapidfuzz.fuzz.ratio`. Alias zawarty w dłuższej etykiecie jako całe słowa daje 0,75 + 0,25 × (udział długości), gdy pokrywa ≥ 50% etykiety. Druga miara to pokrycie: odsetek opcji pola, które są pozycjami słownika (≥ 2 trafienia). Wygrywa najlepszy wynik ≥ `DICT_MATCH_THRESHOLD` (domyślnie **0,8**, zmienna środowiskowa, czytana przez `config("dictionaries.match_threshold")`).
2. Trafienie w słownik `materials`/`user` daje `existing`. Trafienie w słownik `catalog` daje `new` z propozycją zbudowaną z pozycji katalogu.
3. **Nowy słownik z dokumentu.** Gdy nic nie pasuje, a pole ma własne opcje: ≥ 8 opcji, ≥ 90% z nich ma ≤ 4 słowa i żadna nie jest decyzją (TAK/NIE, „zaliczyć…”, „oświadczam…”). Wtedy powstaje propozycja z tych opcji (`source: document`). Pozycje „Inna…/inne” nie trafiają do słownika (to furtka tekstowa).
4. Bez listy pozycji nie ma propozycji (reguła z flow-review). Pole zostaje TEXT_FIELD albo zachowuje własne `options`.

Komponent: `Kraje`, TERYT, `WOJEWODZTWO`, `POWIAT`, `GMINA`, `MIEJSCOWOSC` i `NUMERY_KIERUNKOWE` zawsze dostają SELECT (Reguły techniczne). RADIO z więcej niż 5 pozycjami zamienia się w SELECT. CHECKBOX zostaje (wielokrotny wybór). `searchEnabled` włącza się przy więcej niż 15 pozycjach, a `multiLevelTree` przy więcej niż jednym poziomie.

Pole telefonu: `NUMERY_KIERUNKOWE` jest słownikiem dla osobnego SELECT-a z prefiksem obok numeru. Pole numeru zostaje TEXT_FIELD.

### Wybór metody (zamiast Jev)
METHOD_SECTION

### Wyniki na polach z #1–#9 (test `test_match_forms_1_to_9`)
61/61 zgodnych. Uwaga: aliasy w `catalog.json` pisaliśmy, patrząc na te pola, więc ten wynik mierzy zgodność z regułami, a nie uogólnienie. Uogólnienie sprawdza zestaw kontrolny w sekcji wyżej.

| # | Pole (typ na papierze) | Wynik | Decyzja, wynik | Oczekiwane | |
|---|---|---|---|---|---|
| 1 | Kraj (SELECT) | `Kraje` | existing 1.0 | `Kraje` | ✓ |
| 1 | Województwo (SELECT) | `WOJEWODZTWO` | existing 1.0 | `TERYT_4G_DOWODOWY` / `WOJEWODZTWO` | ✓ |
| 1 | Ulica (TEXT_FIELD) | brak | – | brak | ✓ |
| 1 | Kod pocztowy (TEXT_FIELD) | brak | – | brak | ✓ |
| 1 | Numer budynku (TEXT_FIELD) | brak | – | brak | ✓ |
| 1 | Kraj (SELECT) | `Kraje` | existing 1.0 | `Kraje` | ✓ |
| 1 | Miejscowość (TEXT_FIELD) | `MIEJSCOWOSC` | existing 1.0 | `MIEJSCOWOSC` / brak | ✓ |
| 1 | Numer ewidencyjny działki (TEXT_FIELD) | brak | – | brak | ✓ |
| 1 | Obręb (TEXT_FIELD) | brak | – | brak | ✓ |
| 1 | Numer telefonu (TEXT_FIELD) | `NUMERY_KIERUNKOWE` | existing 1.0 | `NUMERY_KIERUNKOWE` | ✓ |
| 1 | Adres e-mail (TEXT_FIELD) | brak | – | brak | ✓ |
| 2 | Miejscowość (TEXT_FIELD) | `MIEJSCOWOSC` | existing 1.0 | `MIEJSCOWOSC` / `TERYT_4G_DOWODOWY` | ✓ |
| 2 | Nr domu (TEXT_FIELD) | brak | – | brak | ✓ |
| 2 | Nazwa /Imię i nazwisko (TEXT_FIELD) | brak | – | brak | ✓ |
| 2 | NIP (TEXT_FIELD) | brak | – | brak | ✓ |
| 2 | Numer telefonu (TEXT_FIELD) | `NUMERY_KIERUNKOWE` | existing 1.0 | `NUMERY_KIERUNKOWE` | ✓ |
| 2 | Adres poczty elektronicznej (TEXT_FIELD) | brak | – | brak | ✓ |
| 3 | nr telefonu (TEXT_FIELD) | `NUMERY_KIERUNKOWE` | existing 1.0 | `NUMERY_KIERUNKOWE` | ✓ |
| 3 | PESEL (TEXT_FIELD) | brak | – | brak | ✓ |
| 3 | Proszę o wydanie zaświadczenia o (CHECKBOX, 5 opcji) | brak | – | brak | ✓ |
| 3 | Zaświadczenie potrzebne jest celem przedłożenia  (TEXT_FIELD) | brak | – | brak | ✓ |
| 4 | Proszę o (RADIO, 2 opcji) | brak | – | brak | ✓ |
| 4 | Cel wynajęcia świetlicy (TEXT_FIELD) | brak | – | brak | ✓ |
| 4 | Przewidywana ilość uczestników (NUMBER) | brak | – | brak | ✓ |
| 5 | Rodzaj podatku (TEXT_FIELD) | `RODZAJE_PODATKOW_LOKALNYCH` | new 1.0 | `RODZAJE_PODATKOW_LOKALNYCH` / brak | ✓ |
| 5 | Sposób rozliczenia nadpłaty (RADIO, 2 opcji) | brak | – | brak | ✓ |
| 5 | Kwota nadpłaty (NUMBER) | brak | – | brak | ✓ |
| 5 | Kraj (SELECT) | `Kraje` | existing 1.0 | `Kraje` | ✓ |
| 5 | Województwo (SELECT) | `WOJEWODZTWO` | existing 1.0 | `TERYT_4G_DOWODOWY` / `WOJEWODZTWO` | ✓ |
| 6 | w miejscowości (TEXT_FIELD) | `MIEJSCOWOSC` | existing 1.0 | `MIEJSCOWOSC` | ✓ |
| 6 | nazwa drogi oraz jej nr (TEXT_FIELD) | brak | – | brak | ✓ |
| 6 | rodzaj robót i sposób wykonania (TEXTAREA) | brak | – | brak | ✓ |
| 6 | nr telefonu i e-mail (TEXT_FIELD) | `NUMERY_KIERUNKOWE` | existing 0.887 | `NUMERY_KIERUNKOWE` / brak | ✓ |
| 7 | Telefon (TEXT_FIELD) | `NUMERY_KIERUNKOWE` | existing 1.0 | `NUMERY_KIERUNKOWE` | ✓ |
| 7 | Miejscowość (TEXT_FIELD) | `MIEJSCOWOSC` | existing 1.0 | `MIEJSCOWOSC` / `TERYT_4G_DOWODOWY` | ✓ |
| 7 | Rasa psa (TEXT_FIELD) | `RASY_PSOW_AGRESYWNYCH` | new 1.0 | `RASY_PSOW_AGRESYWNYCH` | ✓ |
| 7 | Płeć (RADIO, 2 opcji) | brak | – | brak | ✓ |
| 7 | Sposób oznakowania psa (RADIO, 3 opcji) | brak | – | brak | ✓ |
| 7 | Data urodzenia psa (DATE) | brak | – | brak | ✓ |
| 8 | Składający deklarację (RADIO, 6 opcji) | brak | – | brak | ✓ |
| 8 | PESEL (TEXT_FIELD) | brak | – | brak | ✓ |
| 8 | Kraj (SELECT) | `Kraje` | existing 1.0 | `Kraje` | ✓ |
| 8 | Województwo (TEXT_FIELD) | `WOJEWODZTWO` | existing 1.0 | `WOJEWODZTWO` / `TERYT_4G_DOWODOWY` | ✓ |
| 8 | Gmina (TEXT_FIELD) | `GMINA` | existing 1.0 | `GMINA` / `TERYT_4G_DOWODOWY` | ✓ |
| 8 | Miejscowość (TEXT_FIELD) | `MIEJSCOWOSC` | existing 1.0 | `MIEJSCOWOSC` / `TERYT_4G_DOWODOWY` | ✓ |
| 8 | Numer lokalu (TEXT_FIELD) | brak | – | brak | ✓ |
| 8 | Kraj (TEXT_FIELD) | `Kraje` | existing 1.0 | `Kraje` | ✓ |
| 8 | Okoliczności (RADIO, 4 opcji) | brak | – | brak | ✓ |
| 8 | Rodzaj nieruchomości (RADIO, 2 opcji) | brak | – | brak | ✓ |
| 8 | Nieruchomość w części zamieszkała, w części niez (RADIO, 2 opcji) | brak | – | brak | ✓ |
| 9 | Rodzaj wniosku (RADIO, 3 opcji) | brak | – | brak | ✓ |
| 9 | Wnioskodawca (RADIO, 2 opcji) | brak | – | brak | ✓ |
| 9 | Seria i numer dowodu osobistego (TEXT_FIELD) | brak | – | brak | ✓ |
| 9 | Telefon kontaktowy (opcjonalnie) (TEXT_FIELD) | `NUMERY_KIERUNKOWE` | existing 1.0 | `NUMERY_KIERUNKOWE` | ✓ |
| 9 | Nazwa klubu sportowego (TEXT_FIELD) | brak | – | brak | ✓ |
| 9 | Korespondencja z urzędem (RADIO, 3 opcji) | `SPOSOBY_DORECZENIA` | new 1.0 | `SPOSOBY_DORECZENIA` | ✓ |
| 9 | Poczta tradycyjna - na który adres kierować kore (RADIO, 2 opcji) | brak | – | brak | ✓ |
| 9 | Data urodzenia (DATE) | brak | – | brak | ✓ |
| 9 | Rodzaje dyscyplin sportowych (CHECKBOX, 3 opcji) | `DYSCYPLINY_SPORTOWE` | new 1.0 | `DYSCYPLINY_SPORTOWE` / brak | ✓ |
| 9 | Dyscypliny sportowe (CHECKBOX, 21 opcji) | `DYSCYPLINY_SPORTOWE` | new 1.0 | `DYSCYPLINY_SPORTOWE` | ✓ |
| 9 | Opisz najważniejsze osiągnięcia sportowe kandyda (TEXTAREA) | brak | – | brak | ✓ |
