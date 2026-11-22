# Magazyn danych (SQLAlchemy)

Bazę wybiera `DATABASE_URL` (URL SQLAlchemy 2). Domyślnie to plik SQLite `sqlite:////data/coi.sqlite` na wolumenie `data` z `app/docker-compose.yml`. Na produkcji wystarczy zmienić URL, np. na `postgresql+psycopg://…`, i dodać sterownik do obrazu; kod zostaje ten sam. `DB_PATH=<plik>` działa nadal jako alias dla SQLite. Kod: `backend/coi/store.py`.

## Dostęp
- `from coi.store import Base, Store`. Modele każdego modułu dziedziczą po `Base` (`DeclarativeBase`).
- Instancja jest w `current_app.config["STORE"]`. `Store.engine` to engine SQLAlchemy, a `with Store.session() as s:` robi commit przy sukcesie, rollback przy błędzie i zawsze zamyka sesję (`expire_on_commit=False`).
- Każde wywołanie bierze połączenie z puli engine'u, więc wątki (strumień SSE) nie dzielą sesji.
- `Store.init()` przy starcie aplikacji robi `Base.metadata.create_all` dla wszystkich modeli zaimportowanych do tej chwili. Migracji nie ma; zmiana kolumn wymaga dziś nowej bazy albo ręcznego `ALTER`.
- Każdy moduł obsługuje swoje tabele. Słowniki (`coi/dictionaries/`) mają osobny opis w swoim module.

## Tabela `forms` (model `Form`)
Każdy wynik `POST /api/v1/forms` (A7b). `PUT /api/v1/forms/{id}` nadpisuje `form`.

| Kolumna | Typ | Po co |
|---|---|---|
| `id` | VARCHAR(36) PK | UUID4, używany w `/api/v1/forms/{id}` i w `Location` |
| `title` | VARCHAR(500) | `form.title`, do listy |
| `filename` | VARCHAR(250) | nazwa przesłanego pliku (po walidacji: ≤ 250 znaków, bez znaków zabronionych) |
| `sha256` | VARCHAR(64) | skrót przesłanego pliku: wykrywanie duplikatów i audyt bez trzymania pliku |
| `created_by` | VARCHAR(255) | `sub` z JWT |
| `created_at` | VARCHAR(32), indeks | ISO 8601 UTC z milisekundami; tekst sortuje się tak samo w każdej bazie |
| `updated_by` / `updated_at` | VARCHAR | ostatni `PUT` (NULL, jeśli nikt nie poprawiał) |
| `form` | JSON | czysty JSON COI do importu |
| `report` | JSON | `trace`, `warnings`, `needs_review`, `proposed_dictionaries`, `cost`, `seconds`, `source` |
| `editor` | JSON | `source` (ParsedDocument: strony i bloki tekstu) oraz `field_map` |

Typ `JSON` to w SQLite tekst, a w PostgreSQL natywny `JSON`.

Indeks `ix_forms_created_at` służy liście, która zwraca najnowsze formularze na górze.

## Czego nie zapisujemy
- **Przesłanego pliku.** Backend trzyma upload tylko w pamięci na czas żądania (`InMemoryRequest` w RAM, a nie w pliku tymczasowym Werkzeuga). Poza backendem: nginx frontu może na czas żądania buforować ciało w `/tmp/client_temp` i usuwa je po żądaniu. Parser może na chwilę zapisać PDF w katalogu tymczasowym, żeby wyrenderować strony (Tesseract: `page.png`, `out.txt`, `out.tsv` w `/tmp/tmp*`), i usuwa go po zakończeniu żądania.
- Tokenów JWT ani kluczy LLM.

## Uwaga o `editor.source`
`editor.source` to tekst wyciągnięty z pliku (bloki, tabele, bbox). Nie jest to sam plik, ale jest to jego treść w postaci tekstu. Zapisujemy go, bo `GET /forms/{id}?editor=true` ma pokazać, skąd wzięło się każde pole. Formularze do cyfryzacji to puste wzory urzędowe, a nie wypełnione wnioski obywateli. Jeśli kiedyś trafią tu dane osobowe, `editor` trzeba będzie przestać zapisywać albo wprowadzić retencję.
