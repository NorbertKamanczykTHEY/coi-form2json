# Generator JSON COI: projekt

Status: decyzje Q20–Q24 przyjęte (2026-11-21), kod spike'a jeszcze ich nie uwzględnia · spike: `app/spikes/generator/`

## Decyzje użytkownika

| # | Decyzja | Gdzie w projekcie |
|---|---|---|
| Q20 | S4 (np. #9): zamiast radia „w czyim imieniu” z jedną opcją robimy **CHECKBOX jak na papierze**, a pola podmiotu pokazują się (SHOW), gdy jest zaznaczony | pkt 2 |
| Q21 | `rows` jedną regułą dla wszystkich sekcji: liczba pól + 1 | pkt 3 |
| Q22 | Słownik adresowy to `TERYT_4G_DOWODOWY`, a `TERYT_DOWODOWY` jest jego aliasem. Aliasy są w konfiguracji `coi/config/` | pkt 5, pkt 8 |
| Q23 | Ziarno UUID: `sha256` pliku + techName. Ten sam plik daje te same UUID, różne pliki dają różne | pkt 3 |
| Q24 | „Twoje dane”: MLPZ domyślnie, PESEL jako opcja w konfiguracji | pkt 2, pkt 8 |
| — | „Należy załączyć/dołączyć” i podobne sformułowania dają FILE_UPLOADER (wymagany, R4) | pkt 1 |

Generator jest deterministyczny i nie używa LLM. Dostaje drzewo pól przedmiotu wniosku z metadanymi i zwraca JSON COI oraz kawałek raportu (`field_map`, `proposed_dictionaries`, ostrzeżenia). Ten sam plik wejściowy zawsze daje ten sam JSON, łącznie z UUID.

```
FieldTree (wątek ekstrakcji, Pydantic)
  → resolve: szablony stron + `when` (warianty) + placeholdery + presety + techName
  → słowniki: match() z wątku słowników
  → simplify: warunki na opcjach, których nie ma, znikają; elementy, których nie da się pokazać, wypadają
  → emit: layout (y/rows/questionOrder), UUID, validation, JSONata, flow
  → validate: JSON Schema + reguły 1–6 + referencje JSONaty
```

## 1. Wejście generatora

Przyjmujemy `FieldTree` z `app/spikes/field-extraction/tree.py` (wątek ekstrakcji) **bez zmian w kształcie**. Generator tłumaczy go na swój model wewnętrzny, w tym samym formacie, w jakim zapisane są szablony (pkt 2).

| FieldTree | Generator | Uwagi |
|---|---|---|
| `title` | `title` | sprawdzamy ≤255 znaków i pierwsze słowo (Wniosek/Zgłoszenie/Deklaracja/Oświadczenie) |
| `addressee.kind` `organ`/`office` | `ORGAN`/`URZAD` | wybiera sekcję „Organ…” albo „Urząd…” w szablonie (S1/S1b). `null` → „Urząd”, pusta nazwa i `needs_review` |
| `applicant_kinds` | `PERSON` / `ENTITY` / `ANY` | `[person]` → S2, `[legal_entity]` → S4, oba → S3 |
| `pages[].sections[]` | strony przedmiotu | wstawiane między „Dane” a „Kontakt i zgody” |
| `section.repeating` | `REPEATING_SECTION` | |
| `field.key` | `techName` | po kolizji z innym polem dostaje sufiks z sekcji: `ulica_adres_utrzymania_psa` (jak `ulica_budynku` w #1), potem `_2` |
| `field.optional_evidence` | `required = optional_evidence is None` | R1/R2: `validation: ["REQUIRED", …]` |
| `field.preset` | rozwinięcie z `templates/presets.json` | `pesel` → walidator PESEL, `email` → EMAIL, `address` → blok adresu jak w „Dane”, bez prefillu, z SHOW zależnym od kraju |
| `show_if {field, option}` | `{field, in: [option]}` | wewnętrznie mamy też `not` / `all` / `any`, potrzebne w szablonach |
| `default_value` | `defaultValue` (+ `readOnly`) | S15 |
| `description` | `description` jako `<html>…<p>…</p>…</html>` | dla TEXT_BLOCK to jego treść |
| `consents[]` | dopisane do CONSENT_SECTION na stronie „Kontakt i zgody” | `required: true` (S11) |
| `src`, `doubt` | `report.field_map[fieldId] = {src, needs_review}` | `editor.field_map` z A4 |
| `issues`, `dropped` | `report.warnings` | |
| — (metadane pipeline'u) | `source_sha256` | ziarno UUID (Q23) |

Załączniki: „należy załączyć/dołączyć” i podobne sformułowania dają FILE_UPLOADER z REQUIRED, a „można dołączyć” daje FILE_UPLOADER opcjonalny (`optional_evidence`). Rozpoznaje to ekstrakcja, a generator emituje FILE_UPLOADER bez zmian.

**Prośby do wątku ekstrakcji** (wysłane do jego czatu):
1. `show_if.option` jako lista (`options: [..]`, OR) i `negate: bool`. Potrzebne do „jeśli inny niż…” i CHECKBOX z kilkoma opcjami. Bez tego generator też działa, tylko część warunków wyjdzie słabiej.
2. `key` unikalny w całym drzewie, nie tylko w sekcji, bo `show_if` może wskazywać pole na innej stronie (w spike'u to działa).
3. Pole wewnątrz REPEATING_SECTION może zależeć tylko od pola z tej samej sekcji powtarzalnej albo od pola spoza niej. Pole spoza sekcji powtarzalnej nie może zależeć od pola wewnątrz niej (JSONata COI tego nie wyrazi). Generator zgłasza taki przypadek jako błąd.

## 2. Szablony jako dane

`templates/dane.json`, `templates/kontakt.json`, `templates/finish.json` mają **ten sam format co strony przedmiotu**: sekcje, pola i warunki `show_if` jako dane, nie JSONata. JSONatę dla szablonów i dla przedmiotu buduje ta sama funkcja, więc szablon testuje generator. Szablony powstały skryptem `make_templates.py` ze wzorca #1 (sekcja „Urząd…” i pole PESEL pochodzą z #5). Dalej poprawiamy je ręcznie.

Warianty to dwa mechanizmy, oba w danych:
- `when: {"applicant": ["PERSON","ANY"]}` na sekcji, polu albo opcji. W szablonie „Dane” `when` mają tylko opcje radia „w czyim imieniu” i sekcje adresata.
- Upraszczanie warunków robi resztę. Gdy w wariancie S2 znika opcja „Osoby prawnej…”, każdy warunek na niej daje `false`, więc „Dane podmiotu”, „Adres siedziby”, reprezentant i opłata 2 wypadają same, a warunek pełnomocnictwa skraca się do „Innej osoby”.
- **S4 (Q20):** pole `wybierz_w_czyim_imieniu_wnioskujesz` ma w szablonie drugi wariant: CHECKBOX z `when: {"applicant": ["ENTITY"]}`, ten sam techName i jedną opcją, opcjonalny. Warunki SHOW sekcji podmiotu, reprezentanta i pełnomocnictwa zostają bez zmian, bo `"X" in __userAnswer` działa tak samo dla RADIO i CHECKBOX. Gdy pole jest odznaczone, sekcje podmiotu są ukryte. Etykieta i treść opcji pochodzą z papieru (#9: „Klub sportowy”) przez placeholder `{{entity_option}}`, który generator podstawia w opcji i w warunkach. Bez tekstu z papieru zostaje „Osoby prawnej lub jednostki organizacyjnej”. Spike'owa reguła „radio z jedną opcją znika” do usunięcia.

Placeholdery: `{{addressee.name}}`, `{{entity_option}}`, `{{prefill}}`. To ostatnie to źródło tożsamości w „Twoje dane”: MLPZ domyślnie, PESEL jako opcja w `coi/config/` (Q24). Adres i kontakt zostają przy MLPZ, tak jak w #5.

## 3. Layout i identyfikatory

| Element | Reguła | Wzorce |
|---|---|---|
| `x`, `cols` | 0, 3 | zawsze |
| pole w sekcji | `y` = indeks w sekcji, `rows` 1 | zawsze |
| sekcja | `y` = suma `rows` poprzednich sekcji, `rows` = liczba pól + 1, **dla wszystkich sekcji** (Q21) | zgodne poza sekcjami adresowymi (9 pól: rows 9 albo 8). Tę różnicę akceptujemy |
| `questionOrder` | = `y` | zawsze |
| `description` | sekcja: pusty dokument HTML; pole: `""` | zawsze |
| opcja | `{id: name, name, techName: slug(name)}` | `id` opcji to jej nazwa, nie UUID |
| `techName` | `key` albo slug etykiety: małe litery, `ł→l` itd., `_`, maks. 60 znaków, unikalny w formularzu | |
| UUID | w kształcie v4 z `sha256(source_sha256 / techName)` (Q23). Strona: `source_sha256 / tab / tytuł`, link: `source_sha256 / link / source / target`. Powtarzalny i formalnie poprawny v4 | wzorce: losowe v4 |
| flow | łańcuch linków w kolejności stron | jak we wzorcach |

## 4. JSONata

Warunek wewnętrzny: liść `{field, in: [..]}`, `{not}`, `{all: [..]}`, `{any: [..]}`. Generator najpierw upraszcza warunek, potem emituje JSONatę w nawiasach zgodnych z edytorem COI:
- liść: `("Opcja" in tabs['Strona' in title].questions['sekcja' in field.techName].field.repeatingSectionGrid['pole' in field.techName].field.__userAnswer)`; kilka wartości łączymy `or`;
- liść w sekcji powtarzalnej (przykład 2 z „Reguł technicznych”): `….field.__userAnswer[$repeatingSectionIndex]['pole' in fieldTechName].answers`;
- negacja: `$not(…)`, a `all`/`any` dają `(A) and (B)`;
- wartości i tytuły stron są escapowane (`"` w JSON-ie, `'` w tytule strony).

READ_ONLY ma ten sam kształt (`read_only_if`). Wzorce używają tylko statycznego `readOnly`, więc w praktyce jest rzadki.

## 5. Słowniki i dane inicjalne

Dopasowanie i katalog należą do wątku „Słowniki: dane, SQLite, dopasowanie”. Generator woła jedną funkcję dla każdego pola przedmiotu typu SELECT/RADIO/CHECKBOX oraz TEXT_FIELD z etykietą, która może być słownikowa (rasa, kraj, dyscyplina):

Interfejs uzgodniony z wątkiem słowników (G3gtp), kod: `coi.dictionaries`, opis: `app/docs/dictionaries.md`.

```python
from coi.dictionaries import match, DictMatch
with store.session() as s:          # store = current_app.config["STORE"] albo Store przekazany do pipeline (SSE działa bez app context)
    m = match(s, label, source_label, type, options)   # None = bez słownika
# DictMatch: dictionaryName, decision "existing"|"new", score, reason,
#            component SELECT|RADIO|CHECKBOX, multiLevelTree, searchEnabled,
#            proposal None (słownik istnieje) | {id, name, description, levels, items: [{id?, name, children?}], source: "catalog"|"document"}
```

Reguły komponentu (`component`, `searchEnabled`, `multiLevelTree`) liczy `match`, a generator je przepisuje. Generator wpisuje:
- `type = component`, `dictionaryName`, `options: []`, `multiLevelTree`, `searchEnabled`. TEXT_FIELD, który dostał słownik istniejący (np. „Kraj” w przedmiocie), staje się SELECT-em;
- `proposal` trafia do `report.proposed_dictionaries` (deduplikacja po `id`), a generator dopisuje `fields: [techName…]` (nazwa pola jak w P4 flow-review). Ten obiekt przyjmuje bez zmian `POST /api/v1/dictionaries/from-proposal`;
- `score`, `reason` i `decision` idą do `report.field_map[fieldId]`; jako `needs_review` oznaczamy tylko propozycje nowych słowników (`decision: "new"`);
- warunki SHOW na polu słownikowym nie są sprawdzane względem opcji, bo ich nie znamy.

**Telefon:** `match("Numer telefonu")` zwraca `NUMERY_KIERUNKOWE`, czyli słownik dla osobnego SELECT-a z prefiksem. Generator ignoruje ten wynik dla TEXT_FIELD i pole zostaje tekstowe, tak jak we wzorcach #1 i #5, które prefiksu nie używają. Dodanie SELECT-a z prefiksem przed polem telefonu to ewentualne rozszerzenie, do decyzji.

**Aliasy (Q22):** każdy `dictionaryName`, zarówno z szablonu, jak i z `match`, przechodzi przez mapę aliasów z `coi/config/` (`TERYT_DOWODOWY → TERYT_4G_DOWODOWY`). W wyniku jest zawsze nazwa kanoniczna, więc wszystkie adresy w szablonie dostają `TERYT_4G_DOWODOWY`.

Pola szablonu (Kraje, TERYT) mają słownik w szablonie i nie przechodzą przez `match`. Dane inicjalne są tylko w szablonie („Twoje dane”, adres, kontakt). Pola osób trzecich (S9) nigdy nie dostają prefillu.

## 6. Walidator końcowy (`validate.py`)

1. JSON Schema z materiałów. Prawie nic nie sprawdza (brak `required`, `enum`, `additionalProperties`). Pomijamy znany konflikt: `defaultValue` SELECT jest tablicą.
2. Reguły 1–6: ≥2 strony, ostatnia FINISH; pole tylko w sekcji, bez zagnieżdżeń; brak pól input na FINISH; `validation` jest listą; flow łączy wszystkie strony; każda referencja w JSONacie wskazuje istniejącą stronę, sekcję i pole, a porównywana wartość jest opcją tego pola.
3. Dodatkowo: unikalny `techName`, pole wyboru ma `options` albo `dictionaryName` (nigdy oba).
4. Regresja: `compare.py` porównuje strukturę z #1 i #5 (bez UUID, dzieci po `y`, JSONata bez białych znaków).

Ten sam walidator obsługuje `POST /forms/validate` (A8).

## 7. #9 i flow

Jeden formularz, flow liniowy (linki nie mają warunków, strony nie mają `states`). Na pierwszej stronie przedmiotu jest radio „Rodzaj wniosku”, a sekcje mają SHOW. Warunek między stronami działa, bo JSONata adresuje stronę po tytule (sprawdzone w spike'u). Ograniczenie: strona, której wszystkie sekcje są ukryte, wyświetli się pusta. Ekstrakcja powinna więc dzielić #9 na strony tematyczne wspólne dla wariantów, a nie na strony per wariant. Generator ostrzega, gdy wszystkie sekcje strony mają SHOW.

## 8. Konfiguracja (`coi/config/`)

Całą konfigurację generatora trzymamy w jednym miejscu, na wzór `config/` z Laravela. Generator czyta z niej:
- `prefill_identity`: `MLPZ` (domyślnie) albo `PESEL` (Q24);
- `dictionary_aliases`: `{"TERYT_DOWODOWY": "TERYT_4G_DOWODOWY"}` (Q22);
- ścieżkę do szablonów (`templates/`) i presetów.

Szablony i presety zostają plikami danych obok kodu, a konfiguracja wskazuje tylko, skąd je brać.

## Wynik spike'a

Spike powstał przed decyzjami Q20–Q24, więc ma jeszcze regułę „radio z jedną opcją znika”, ziarno UUID z tytułu i TERYT jak w #1.

| Test | Wynik |
|---|---|
| #1 z szablonu + drzewa przedmiotu | 56 różnic, 3 klasy: `validation` (37, celowo REQUIRED/R6), `rows` 3 sekcji adresowych (+1/+2) i przesunięte `y`/`questionOrder` (19), tytuł „Kontakt i zgody” zamiast „Kontakt z urzędem”. **Wszystkie 24 JSONaty identyczne**, łącznie z warunkiem `A or (B and C)` przy pełnomocnictwie |
| #5 | 76 różnic: te same klasy plus różnice między samymi wzorcami (TERYT_DOWODOWY ↔ 4G, `searchEnabled`, nazwy plików, REGON/KRS w „Dane podmiotu”, treść podglądu) |
| Warianty S2/S4 na #1 | S2: znikają sekcje podmiotu, radio „jako kto” i opłata 2. S4: znika radio „w czyim imieniu”, dane innej osoby i opłata 1. Pełnomocnictwo dostaje uproszczony warunek |
| Próbka (S2, REPEATING_SECTION, CHECKBOX „inne”, `$not`, warunek między stronami, zgoda z dokumentu) | poprawna JSONata `[$repeatingSectionIndex]`, walidator OK |
| Determinizm | dwa uruchomienia dają identyczny SHA |
| Walidator na wzorcach | #5 OK. #1: 3 pola z `validation: {}` |

Błąd wychwycony przez diff: w #5 PESEL zasila tylko tożsamość, a adres nadal ma `MLPZ.*`. Szablon to uwzględnia.

## Rozbieżności w materiałach

| Rozbieżność | Co robimy |
|---|---|
| Schemat `repetingSectionGrid`, wzorce `repeatingSectionGrid` | emitujemy jak wzorce |
| `validation: {}` w #1 (3 pola), `[]` wszędzie indziej | zawsze lista; REQUIRED według R1–R7 |
| Schemat: `defaultValue` to string, wzorce: SELECT `["Polska"]` | jak wzorce; walidator pomija ten konflikt |
| Schemat: `consentSectionConfig.required` obok `consents` (we wzorcach w każdej zgodzie) | jak wzorce |
| `multiLevelTree`, `searchEnabled`, `minItemRows` poza schematem | emitujemy, gdy słownik lub szablon je ma |
| TERYT_DOWODOWY kontra TERYT_4G_DOWODOWY: niespójne nawet w obrębie jednego wzorca | wszędzie `TERYT_4G_DOWODOWY`, a stara nazwa jest aliasem (Q22) |
| Reguła: na FINISH „wyłącznie INFO_SECTION”, wzorce: SECTION + TEXT_BLOCK | jak wzorce; walidator dopuszcza TEXT_BLOCK |
| Opcja w #5 bez `techName`; link w #5 z id `a16ec` | zawsze pełne |
| Kontakt z prefillem MLPZ, edytowalny | jak wzorce |

## Zmiany w kodzie po decyzjach (do zrobienia przy implementacji)

1. Q20: wariant CHECKBOX w `templates/dane.json`, placeholder `{{entity_option}}`, usunięcie reguły „radio z jedną opcją znika” z `gen.py`.
2. Q22: zamiana nazw TERYT w szablonie i mapa aliasów w `coi/config/`.
3. Q23: `stable_id(source_sha256, …)` zamiast tytułu formularza.
4. Q24: `prefill` z `coi/config/`, domyślnie MLPZ.
5. Telefon: ignorowanie `NUMERY_KIERUNKOWE` dla TEXT_FIELD, chyba że zdecydujemy o SELECT-cie z prefiksem.
