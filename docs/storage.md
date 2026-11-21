# Magazyn danych (SQLite)

Jeden plik SQLite pod `DB_PATH` (domyślnie `/data/coi.sqlite`, wolumen `data` w `app/docker-compose.yml`). Bez ORM, tylko stdlib `sqlite3`. Kod: `backend/coi/store.py`.

## Dostęp
- `Store.connect()` zwraca nowe połączenie (`row_factory = sqlite3.Row`). Wołający sam robi commit i zamyka połączenie.
- `with Store.db() as con:` robi commit przy sukcesie, rollback przy błędzie i zawsze zamyka połączenie.
- Instancja jest w `current_app.config["STORE"]`. Każde wywołanie otwiera krótkie połączenie, więc wątki (strumień SSE) nie dzielą obiektu połączenia.
- `Store.init()` przy starcie aplikacji tworzy brakujące tabele (`CREATE TABLE IF NOT EXISTS`). Migracji nie ma.
- Każdy moduł zakłada i obsługuje swoje tabele. Słowniki (`coi/dictionaries/`) mają osobny opis w swoim module.

## Tabela `forms`
Każdy wynik `POST /api/v1/forms` (A7b). `PUT /api/v1/forms/{id}` nadpisuje `form`.

| Kolumna | Typ | Po co |
|---|---|---|
| `id` | TEXT PK | UUID4, używany w `/api/v1/forms/{id}` i w `Location` |
| `title` | TEXT | `form.title`, do listy |
| `filename` | TEXT | nazwa przesłanego pliku (po walidacji: ≤ 250 znaków, bez znaków zabronionych) |
| `sha256` | TEXT | skrót przesłanego pliku: wykrywanie duplikatów i audyt bez trzymania pliku |
| `created_by` | TEXT | `sub` z JWT |
| `created_at` | TEXT | ISO 8601 UTC |
| `updated_by` / `updated_at` | TEXT | ostatni `PUT` (NULL, jeśli nikt nie poprawiał) |
| `form` | TEXT (JSON) | czysty JSON COI do importu |
| `report` | TEXT (JSON) | `trace`, `warnings`, `needs_review`, `proposed_dictionaries`, `cost`, `seconds`, `source` |
| `editor` | TEXT (JSON) | `source` (ParsedDocument: strony i bloki tekstu) oraz `field_map` |

Indeks `forms_created_at` służy liście, która zwraca najnowsze formularze na górze.

## Czego nie zapisujemy
- **Przesłanego pliku.** Plik istnieje tylko w pamięci na czas żądania (`InMemoryRequest` trzyma upload w RAM, a nie w pliku tymczasowym Werkzeuga). Parser może na chwilę zapisać PDF w katalogu tymczasowym, żeby wyrenderować strony, i usuwa go po zakończeniu żądania.
- Tokenów JWT ani kluczy LLM.

## Uwaga o `editor.source`
`editor.source` to tekst wyciągnięty z pliku (bloki, tabele, bbox). Nie jest to sam plik, ale jest to jego treść w postaci tekstu. Zapisujemy go, bo `GET /forms/{id}?editor=true` ma pokazać, skąd wzięło się każde pole. Formularze do cyfryzacji to puste wzory urzędowe, a nie wypełnione wnioski obywateli. Jeśli kiedyś trafią tu dane osobowe, `editor` trzeba będzie przestać zapisywać albo wprowadzić retencję.
