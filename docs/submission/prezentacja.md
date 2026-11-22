---
marp: true
paginate: true
size: 16:9
style: |
  section { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 26px; padding: 50px 64px; color: #1b2430; }
  h1 { color: #0b4f8a; font-size: 42px; margin-bottom: 12px; }
  h2 { color: #0b4f8a; font-size: 34px; }
  table { font-size: 20px; }
  th { background: #0b4f8a; color: #fff; }
  code { font-size: 0.9em; }
  .src { position: absolute; bottom: 26px; left: 64px; font-size: 15px; color: #6b7785; }
  .flow { display: flex; gap: 12px; align-items: stretch; margin: 18px 0; }
  .box { flex: 1; border: 2px solid #0b4f8a; border-radius: 10px; padding: 10px 12px; font-size: 19px; background: #eef5fc; }
  .box b { display: block; color: #0b4f8a; font-size: 22px; margin-bottom: 4px; }
  .arrow { align-self: center; font-size: 30px; color: #0b4f8a; }
  .big { font-size: 46px; white-space: nowrap; color: #0b4f8a; font-weight: 700; line-height: 1.05; }
  .cols { display: flex; gap: 36px; }
  .cols > div { flex: 1; }
  .shots { display: flex; gap: 18px; margin-top: 8px; }
  .shots figure { flex: 1; margin: 0; font-size: 17px; color: #4a5563; }
  .shots img { width: 100%; border: 1px solid #c9d3de; border-radius: 6px; }
  .warn { border-left: 6px solid #b5481f; background: #fbf1ec; padding: 8px 14px; font-size: 21px; }
---

<!-- _paginate: false -->

# Blankiet → e-usługa

## Formularz urzędowy w JSON COI w mniej niż minutę

Jeden plik (PDF, DOC, DOCX, ODS, XLSX, JPG, PNG) → JSON gotowy do importu w Generatorze Formularzy COI

REST API · edytor z uwagami do decyzji · makieta dla obywatela · Docker · tryb air gap

---

# Problem

- Urzędnik przepisuje papierowy wniosek do Generatora Formularzy **ręcznie**: strony, sekcje, pola, walidatory, słowniki, warunki „pokaż, jeśli…”
- Formularz #9 (stypendium): **trzy wnioski w jednym**, około 100 pól
- Każda pomyłka to zła e-usługa dla mieszkańca, a Standardy COI trzeba znać na pamięć

**Cel:** plik blankietu na wejściu, poprawny JSON COI i lista rzeczy do sprawdzenia na wyjściu.

<div class="src">Źródło: materials/COI - Pełna treść zadania konkursowego.pdf; app/results/README.md (#9: 100 pól, EVAL-5)</div>

---

# Architektura: parse → extract → generate → validate

<div class="flow">
<div class="box"><b>parse</b>Kreuzberg, Tesseract <code>pol</code> lokalnie. VLM tylko dla stron, które odrzuci bramka<br/>→ <code>ParsedDocument</code></div>
<div class="arrow">→</div>
<div class="box"><b>extract</b>LLM buduje pola z kotwicą w źródle. Bramka, naprawa, mocniejszy model<br/>→ <code>FieldTree</code></div>
<div class="arrow">→</div>
<div class="box"><b>generate</b>Deterministycznie, bez LLM: szablony stron, słowniki, walidatory, JSONata SHOW<br/>→ JSON COI</div>
<div class="arrow">→</div>
<div class="box"><b>validate</b>Schemat zadania, reguły R1–R6, unikalne <code>techName</code>, odwołania JSONata</div>
</div>

- 2 kontenery (backend Flask + gunicorn, frontend React + nginx), oba bez roota, wersje przypięte
- Jedno REST API: OpenAPI 3.1, Swagger `/docs`, błędy RFC 9457, postęp przez SSE
- Plik tylko w pamięci; w bazie zostaje wynik, nazwa i sha256 pliku

<div class="src">Źródło: app/docs/architecture.md, ADR 0003, 0013, 0014, 0016</div>

---

# Koszt: ile i jak go zbiliśmy

<div class="cols"><div style="flex:1.4">

1. **Tekst czytamy lokalnie, za darmo:** Kreuzberg (Word, PDF), Tesseract (skany), własny odczyt XML arkuszy
2. **Model tylko, gdy trzeba:** wołamy go dopiero wtedy, gdy kod odrzuci tańszy wynik
3. **Najpierw mały i tani model:** ministral-8b przy skanach, mistral-small przy polach; większy dopiero po porażce
4. **Długi wniosek po stronach, równolegle:** #8 ze 184.5 s (EVAL-3) do 42.8 s (EVAL-5, mediana)

</div><div>

<span class="big">$0.27</span><br/>komplet 11 formularzy, ok. 2,4 centa na formularz

<span class="big">$0.81</span><br/>pełny test EVAL-5: 11 plików × 3 przebiegi

</div></div>

Przy modelu w sieci urzędu (`LLM_PROVIDER=local`) koszt API wynosi zero, płaci się tylko za GPU.

<div class="src">Źródło: app/docs/architecture.md (Drabina eskalacji, Koszt na formularz), app/backend/coi/parsing/pipeline.py (sheet-xml), app/results/eval-5/README.md ($0.2660, $0.8071)</div>

---

# Kompletność: minimum i rozszerzenia I–VI

| Wymaganie | Stan | Dowód |
|---|---|---|
| M1–M3: 8 formatów, JSON zgodny ze schematem i wzorcami | ✅ | 33/33 wywołań przechodzi walidację (EVAL-5) |
| M4: Standardy i Reguły techniczne | 🟡 | Rozb. krytyczne 22 → 12 → 12 (EVAL-3/4/5) |
| M5: dokumentacja | ✅ | architecture.md, 27 ADR-ów |
| I: słowniki i dane inicjalne | ✅ | Kraje, TERYT, gminy; `MLPZ.*` |
| II: propozycja słownika | ✅ | #5, #7, #9; „Przyjmij słownik” w edytorze |
| III: zależności | 🟡 | 382 warunki SHOW (JSONata); flow stron liniowy |
| IV, V: front i podgląd e-usługi | ✅ | import wsadowy, edytor, makieta ze SHOW |
| VI: walidatory i UX | 🟡 | PESEL, NIP, REGON, kod, e-mail, ePUAP…; brak telefonu |

<div class="src">Źródło: app/docs/compliance.md, app/results/eval-5/README.md, app/results/*.coi.json</div>

---

# Intuicyjność: urzędnik widzi, co sprawdzić

<div class="shots">
<figure><img src="img/clean-import-log.png"/>Import kilku plików w tle, log etapów z czasem i kosztem</figure>
<figure><img src="img/clean-editor-note-1.png"/>Uwaga do decyzji: powód, „Co zrobić” i „Akceptuję bez zmian”</figure>
<figure><img src="img/clean-mockup.png"/>Jeden edytor na makiecie: „Podgląd” działa jak e-usługa, „Edycja” zmienia pola</figure>
</div>

Po poprawce formularz przebudowuje się **bez ponownego LLM**. Zero cichych porażek.

<div class="src">Źródło: app/docs/submission/img/clean-*.png, ADR 0014, ADR 0027</div>

---

# Wyniki EVAL-5: jakość, czas, koszt

<div class="cols"><div style="flex:0 0 30%">

<span class="big">22 → 12 → 12</span><br/>rozbieżności krytyczne<br/>EVAL-3 / 4 / 5

<span class="big">$0.27</span><br/>komplet 11 plików, średnio 2,4 centa na formularz

</div><div>

| Formularz | Pola | Czas mediana [s] | < 60 s | Koszt [$] |
|---|---|---|---|---|
| #1 wzorzec (docx) | 54 | 10.0 | 3/3 | 0.0028 |
| #3 zaświadczenie (docx) | 38 | 16.1 | 3/3 | 0.0037 |
| #6 pas drogowy (docx) | 85 | 72.2 | 1/3 | 0.0142 |
| #8 odpady (docx) | 93 | **42.8** | 2/3 | 0.0670 |
| #9 stypendium (docx) | 100 | **39.7** | 3/3 | 0.0674 |
| #7 skan (jpg) | 54 | 92.7 | 0/3 | 0.0162 |
| #9 skan (png) | 99 | 98.6 | 0/3 | 0.0716 |

</div></div>

3 przebiegi na plik, sekwencyjnie. Pola i koszt z przebiegu mediany.

<div class="src">Źródło: app/results/eval-5/README.md, app/results/eval-5/zmiennosc.md, app/results/README.md</div>

---

# Jakość kodu i uczciwe ograniczenie

<div class="cols"><div>

- Dwa kontrakty: `ParsedDocument` i `FieldTree`
- Generator deterministyczny, **nie zna numeru formularza**
- **302 testy** bez sieci, test trybu air gap
- **27 ADR-ów**: Standardy COI > wzorce #1/#5 > ADR
- Python 3.14, licencje bez copyleftu
- Oceny eksperckie EVAL-3…5, reguły posortowane po zysku

</div><div>

<div class="warn">

**Stabilność między przebiegami.** Bramka przeszła 3/3 tylko w #1. W #8 dwa z trzech przebiegów gubią dwie sekcje papieru.

**Jak to adresujemy:** bramka nie przepuszcza złego wyniku po cichu, `needs_review` wskazuje miejsce w źródle, edytor daje decyzję urzędnikowi, a kolejne reguły przechodzą z promptu do deterministycznego generatora.

</div>

</div></div>

<div class="src">Źródło: app/results/eval-5/README.md (Zmienność), app/docs/adr/, pytest -m "not eden"</div>

---

# Potencjał wdrożeniowy

<div class="cols"><div>

- **Air gap:** `LLM_PROVIDER=local` + Ollama / vLLM w sieci urzędu, zero ruchu wychodzącego
- **IdP urzędu:** JWT RS256 z JWKS, kontrola `iss`, `aud`, `exp`
- **Baza:** SQLite albo PostgreSQL przez `DATABASE_URL` (SQLAlchemy)

</div><div>

- **Prompty w plikach `.md`**: urząd dopisuje własne reguły bez programisty
- **Drabina modeli w konfiguracji**: `ladder.json`, `EXTRACTION_LADDER`
- **Jedno API** dla frontu, systemu COI i agentów AI

</div></div>

**Koszt:** średnio 2,4 centa na formularz w chmurze, $0 API w trybie lokalnym (tylko GPU).

<div class="src">Źródło: app/README.md (Konfiguracja, Tryb air gap), ADR 0010, 0015, 0017; koszt: app/results/README.md</div>

---

<!-- _paginate: false -->

# Blankiet → e-usługa

- Minimum i rozszerzenia I–VI (III i VI częściowo, z ograniczeniami schematu)
- #9 w 40 s, #8 w 43 s (mediana); komplet 11 plików za $0.27
- Drabina eskalacji: droższy model tylko wtedy, gdy kod odrzuci tańszy wynik
- Edytor z uwagami do decyzji i regeneracją bez LLM
- Gotowe do air gap i logowania przez IdP urzędu

**Kod:** `app/` · **Swagger:** `/docs` · **Wyniki i oceny:** `app/results/`
