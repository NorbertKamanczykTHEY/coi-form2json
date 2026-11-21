# 0027. „Tylko osobiście” z dokumentu, przełącznik w edytorze bez ponownego LLM
Data: 2026-11-21 · Status: przyjęta · Decyzja: Q16
Źródło: UŻYTKOWNIK, na podstawie `research/2026-11-21-pelnomocnik.md` (pkt 3–5)

## Kontekst
- Szablon „Dane” zawsze daje „Podmiot wniosku” z opcją „Innej osoby”, pełnomocnictwo i opłatę skarbową. Standardy s.9: „Jeżeli można wnioskować tylko we własnym imieniu – pomiń tę sekcję”.
- Sygnał „tylko osobiście” jest rzadki i może być źle odczytany przez model, więc urzędnik musi móc go zmienić bez ponownej konwersji.

## Decyzja
1. Generator czyta z FieldTree `applicant_self_only` (domyślnie `false`) i `applicant_self_only_src` (kotwice cytatu). Ekstrakcja ustawia `true` tylko na wyraźny sygnał z cytatem. Przy `true` szablon nie ma opcji „Innej osoby” ani „Pełnomocnik”, sekcji pełnomocnictwa ani opłaty skarbowej. Dla osoby fizycznej znika cała sekcja „Podmiot wniosku” (reguła „pole wyboru z jedną opcją znika”, ADR 0026), a podmiot działa tylko przez reprezentanta.
2. `POST /api/v1/forms` zapisuje w `editor` drzewo (`tree`), surowe `needs_review` ekstrakcji i ostrzeżenia parsowania. `POST /api/v1/forms/{id}/regenerate` z `{"applicant_self_only": bool}` przebudowuje JSON z zapisanego drzewa (bez parsowania i bez LLM) i zapisuje go w miejsce poprzedniego, razem z raportem i danymi edytora. Formularz zapisany wcześniej, bez drzewa, daje 409 `no_stored_tree`.
3. `editor.applicant_self_only` = `{value, source, quote}`, gdzie `source` to `dokument` (z cytatem), `domyślnie` albo `edytor`.

## Konsekwencje
- Ręczne poprawki JSON-a zapisane przez `PUT` przepadają przy `regenerate`, bo formularz powstaje od nowa z drzewa. Edytor powinien o tym uprzedzić.
- Ten sam endpoint może przyjmować kolejne nadpisania ustawień generatora bez zmian w API.
