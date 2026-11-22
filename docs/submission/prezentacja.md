---
marp: true
paginate: true
size: 16:9
style: |
  section { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 26px; padding: 50px 64px; color: #1b2430; }
  h1 { color: #0b4f8a; font-size: 44px; margin-bottom: 12px; }
  h2 { color: #0b4f8a; font-size: 34px; }
  table { font-size: 21px; }
  th { background: #0b4f8a; color: #fff; }
  code { font-size: 0.9em; }
  .src { position: absolute; bottom: 28px; left: 64px; font-size: 15px; color: #6b7785; }
  .flow { display: flex; gap: 12px; align-items: stretch; margin: 18px 0; }
  .box { flex: 1; border: 2px solid #0b4f8a; border-radius: 10px; padding: 10px 12px; font-size: 19px; background: #eef5fc; }
  .box b { display: block; color: #0b4f8a; font-size: 22px; margin-bottom: 4px; }
  .arrow { align-self: center; font-size: 30px; color: #0b4f8a; }
  .big { font-size: 64px; color: #0b4f8a; font-weight: 700; line-height: 1; }
  .cols { display: flex; gap: 40px; }
  .cols > div { flex: 1; }
  .todo { color: #b5481f; font-weight: 600; }
---

<!-- _paginate: false -->

# Blankiet → e-usługa

## Formularz urzędowy w JSON COI w kilka minut, za około 2 centy

Jeden plik (PDF, DOC, DOCX, ODS, XLSX, JPG, PNG) → JSON gotowy do importu w Generatorze Formularzy COI

REST API · podgląd e-usługi · raport pól do sprawdzenia · Docker · tryb air gap

---

# Problem

- Urzędnik przepisuje papierowy wniosek do Generatora Formularzy **ręcznie**: strony, sekcje, pola, walidatory, słowniki, warunki „pokaż, jeśli…”
- Formularz #9 (stypendium): **151 pól**, trzy wnioski w jednym
- Każda pomyłka to zła e-usługa dla mieszkańca, a Standardy COI trzeba znać na pamięć

**Cel:** plik blankietu na wejściu, poprawny JSON COI i lista rzeczy do sprawdzenia na wyjściu.

<div class="src">Źródło: materials/COI - Pełna treść zadania konkursowego.pdf; results/summary.json (#9: 151 pól)</div>

---

# Architektura: parse → extract → generate → validate

<div class="flow">
<div class="box"><b>parse</b>Kreuzberg, Tesseract <code>pol</code> lokalnie. VLM tylko dla stron, które odrzuci bramka<br/>→ <code>ParsedDocument</code></div>
<div class="arrow">→</div>
<div class="box"><b>extract</b>LLM buduje pola z kotwicą w źródle. Bramka G1–G17, naprawa, mocniejszy model<br/>→ <code>FieldTree</code></div>
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

# Drabina eskalacji z bramką jakości

<div class="cols"><div>

**Parsowanie strony**
1. Kreuzberg / Tesseract (lokalnie, 0 zł)
2. ministral-8b → 14b → mistral-small → mistral-large

Tesseract jest **świadkiem**: VLM, który zmyśla tekst, przegrywa porównanie pokrycia słów.

</div><div>

**Ekstrakcja pól**
1. mistral-small
2. runda naprawy z listą zarzutów
3. mistral-large + naprawa

Bramka: schemat Pydantic, kotwice, pokrycie bloków `☐`/`___`, poprawność `show_if`, ugruntowanie etykiet.

</div></div>

Droższy model startuje **tylko**, gdy kod odrzuci wynik. Timeout liczy się jako nieudany szczebel, a nie błąd żądania.

<div class="src">Źródło: app/docs/architecture.md (Drabina eskalacji i bramki), ADR 0007, 0008</div>

---

# Kompletność: minimum i rozszerzenia I–VI

| Wymaganie | Stan | Dowód |
|---|---|---|
| M1–M3: 8 formatów, JSON zgodny ze schematem i wzorcami | ✅ | 11/11 plików przechodzi walidację |
| M4: Standardy i Reguły techniczne | 🟡 | EVAL-3: 22 rozb. krytyczne w #2–#9 <span class="todo">TODO(EVAL-4)</span> |
| M5: dokumentacja | ✅ | architecture.md, 27 ADR-ów |
| I: słowniki i dane inicjalne | ✅ | Kraje, TERYT, gminy; `MLPZ.*` |
| II: propozycja słownika | ✅ | #5, #7, #9 w raporcie, przyjęcie 1 kliknięciem |
| III: zależności | 🟡 | 438 warunków SHOW (JSONata); flow stron liniowy |
| IV, V: front i podgląd e-usługi | ✅ | batch, SSE, JSON, podgląd ze SHOW |
| VI: walidatory i UX | 🟡 | PESEL, NIP, REGON, kod, e-mail, ePUAP…; brak telefonu |

<div class="src">Źródło: app/docs/compliance.md, app/results/README.md</div>

---

# Intuicyjność: urzędnik widzi, co sprawdzić

- Wczytanie **kilku plików naraz**, postęp każdego etapu na żywo (SSE)
- **Podgląd e-usługi**: strony, sekcje, sekcje powtarzalne, słowniki; warunki SHOW działają jak po imporcie
- **Raport `needs_review`** z mapą źródła: pole → strona i blok papieru
- Poprawka, zapis i **regeneracja bez ponownego LLM**
- Zero cichych porażek: błąd, ostrzeżenie albo pozycja do sprawdzenia, zawsze widoczne

<span class="todo">TODO(screenshot): podgląd e-usługi i raport w nowym froncie</span>

<div class="src">Źródło: app/README.md, ADR 0014, ADR 0027</div>

---

# Wyniki: czas i koszt na formularz

| Formularz | Format | Pola | Czas [s] | Koszt [$] |
|---|---|---|---|---|
| #3 zaświadczenie | docx | 36 | 4.6 | 0.0014 |
| #1 numer porządkowy (wzorzec) | docx | 53 | 10.1 | 0.0032 |
| #6 pas drogowy | docx | 70 | 69.2 | 0.0145 |
| #8 deklaracja odpady | docx | 120 | 184.5 | 0.0573 |
| #9 stypendium (3 w 1) | docx | 151 | 224.7 | 0.0666 |
| #7 skan | jpg | 46 | 60.1 | 0.0097 |
| #9 skan | png | 144 | 171.2 | 0.0599 |

<div class="cols"><div><span class="big">$0.25</span><br/>11 plików, średnio ~2 centy na formularz</div><div><span class="big">11/11</span><br/>przechodzi walidację schematu</div></div>

<span class="todo">TODO(EVAL-4): liczby z app/results/eval-4/</span>

<div class="src">Źródło: app/results/README.md, app/results/summary.json</div>

---

# Jakość kodu

- Dwa jawne kontrakty: `ParsedDocument` (parser) i `FieldTree` (ekstrakcja → generator)
- Generator deterministyczny, **nie zna numeru formularza**: reguły wynikają z treści
- **261 testów** bez sieci (`pytest -m "not eden"`), test trybu air gap
- **27 ADR-ów**: każda decyzja z uzasadnieniem i źródłem (Standardy COI > wzorce #1/#5 > ADR)
- Python 3.14, uv, tylko licencje bez copyleftu
- Ocena ekspercka EVAL-3: reguły G1–G17 posortowane po zysku, wdrażane po kolei

<div class="src">Źródło: app/docs/compliance.md (Weryfikacja), app/docs/adr/, app/results/eval-3/README.md, ADR 0024</div>

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

**Koszt:** ~2 centy na formularz w chmurze, $0 API w trybie lokalnym (tylko GPU).

<div class="src">Źródło: app/README.md (Konfiguracja, Tryb air gap), ADR 0010, 0015, 0017</div>

---

<!-- _paginate: false -->

# Blankiet → e-usługa

- Pełne minimum i rozszerzenia I–VI (III i VI częściowo, z ograniczeniami schematu)
- Drabina eskalacji: droższy model tylko wtedy, gdy kod odrzuci tańszy wynik
- Edytor z mapą źródła i regeneracją bez LLM
- ~2 centy na formularz, gotowe do air gap

**Repozytorium:** `app/` · **Swagger:** `/docs` · **Wyniki:** `app/results/`

<span class="todo">TODO: link do repozytorium i filmu</span>
