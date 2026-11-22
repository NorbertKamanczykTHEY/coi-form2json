---
marp: true
paginate: true
size: 16:9
style: |
  section { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 28px; padding: 44px 56px; color: #1b2430; }
  h1 { color: #0b4f8a; font-size: 40px; margin: 0 0 14px; }
  code { font-size: 0.9em; }
  .duo { display: flex; gap: 28px; }
  .duo > div { flex: 1; }
  .duo h3 { color: #0b4f8a; font-size: 26px; margin: 0 0 8px; }
  .duo p { font-size: 21px; margin: 10px 0 0; line-height: 1.35; }
  .shot { width: 100%; height: 330px; object-fit: cover; object-position: top; border: 1px solid #c9d3de; border-radius: 8px; box-shadow: 0 4px 14px rgba(11,79,138,.12); }
  .shot.bottom { object-position: bottom; }
  .card { height: 330px; box-sizing: border-box; border: 2px solid #0b4f8a; border-radius: 8px; background: #eef5fc; padding: 18px 20px; font-size: 21px; }
  .step { background: #fff; border: 1px solid #9fb9d3; border-radius: 6px; padding: 7px 12px; margin: 6px 0; }
  .step.gate { border-color: #b5481f; color: #b5481f; font-weight: 600; text-align: center; background: #fbf1ec; }
  .card pre { font-size: 17px; margin: 8px 0; }
  .flow { display: flex; gap: 12px; align-items: center; margin-top: 26px; }
  .box { flex: 1; border: 2px solid #0b4f8a; border-radius: 12px; padding: 16px 12px; text-align: center; background: #eef5fc; font-size: 20px; }
  .box b { display: block; color: #0b4f8a; font-size: 26px; margin-bottom: 6px; }
  .end { flex: 1; border-radius: 12px; padding: 16px 12px; text-align: center; font-size: 22px; font-weight: 700; background: #0b4f8a; color: #fff; }
  .arrow { font-size: 34px; color: #0b4f8a; }
  .nums { display: flex; gap: 30px; margin-top: 30px; }
  .nums > div { flex: 1; text-align: center; border-top: 6px solid #0b4f8a; padding-top: 16px; font-size: 22px; color: #4a5563; }
  .big { display: block; font-size: 64px; font-weight: 700; color: #0b4f8a; line-height: 1.1; white-space: nowrap; }
  .lead { font-size: 34px; color: #4a5563; }
  .src { position: absolute; bottom: 24px; left: 56px; font-size: 15px; color: #6b7785; }
  section.hero { justify-content: center; text-align: center; }
  section.hero h1 { font-size: 64px; }
  .mono { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 64px; color: #0b4f8a; font-weight: 700; margin: 24px 0; }
  .links { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 30px; line-height: 1.7; }
---

<!-- _class: hero -->
<!-- _paginate: false -->

# Blankiet → e-usługa

<p class="lead">Wrzucasz papierowy formularz, a w niecałą minutę dostajesz e-usługę gotową do importu w Generatorze Formularzy COI.</p>

---

# Problem

<div class="duo"><div>

- Urzędy trzymają **wnioski na papierze**: w Wordzie, PDF-ach i skanach
- Każdy trzeba **ręcznie** przepisać do Generatora Formularzy: strony, pola, walidatory, słowniki, warunki
- Formularz #9 (stypendium) to **trzy wnioski w jednym**

</div><div>

<img class="shot" src="img/03-list-new.png"/>
<p>Z nami: lista formularzy przeniesionych z papieru i liczba uwag do decyzji przy każdym</p>

</div></div>

---

# Rozwiązanie: jeden plik → JSON e-usługi

<div class="flow">
<div class="box"><b>📄</b>PDF · DOC(X) · ODS · XLSX · JPG · PNG</div>
<div class="arrow">→</div>
<div class="box"><b>parse</b>tekst lokalnie, OCR</div>
<div class="arrow">→</div>
<div class="box"><b>extract</b>LLM + bramka jakości</div>
<div class="arrow">→</div>
<div class="box"><b>generate</b>bez LLM, szablony COI</div>
<div class="arrow">→</div>
<div class="box"><b>validate</b>schemat + reguły</div>
<div class="arrow">→</div>
<div class="end">JSON COI<br/>+ raport</div>
</div>

<p class="lead" style="margin-top:40px">Jedno REST API, dwa kontenery Docker, frontend dla urzędnika.</p>

---

# Import i uwagi do decyzji

<div class="duo"><div>

### Import wielu plików w tle
<img class="shot" src="img/01-import-running.png"/>
<p>Wrzucasz kilka plików, zamykasz okno, a import trwa dalej z logiem każdego etapu.</p>

</div><div>

### Czerwone uwagi do decyzji
<img class="shot" src="img/04-editor-red-marks.png"/>
<p>Pole, którego bramka nie jest pewna, ma powód i przycisk „Akceptuję bez zmian”.</p>

</div></div>

---

# Makieta i edycja

<div class="duo"><div>

### Makieta dla obywatela
<img class="shot" src="img/06-mockup-show.png"/>
<p>E-usługa wygląda tak jak po imporcie, z działającymi warunkami pokazywania pól.</p>

</div><div>

### Edycja na makiecie
<img class="shot" src="img/14-structure-edit.png"/>
<p>Etykiety, opcje, wymagalność, dodawanie i usuwanie pól i sekcji z cofaniem.</p>

</div></div>

---

# Warunki i słowniki

<div class="duo"><div>

### Edytor warunków JSONata
<img class="shot" src="img/14-condition-graphic.png" style="object-position: center"/>
<p>Konstruktor graficzny ⇄ tekst JSONata, sprawdzane na bieżąco i opisane słowami.</p>

</div><div>

### Słowniki i dane inicjalne
<img class="shot" src="img/06-mockup-show.png" style="object-position: 0 85%"/>
<p>Kraje, TERYT i gminy z katalogu, dane z profilu (<code>MLPZ.*</code>), nowy słownik jako propozycja.</p>

</div></div>

---

# Silnik i wdrożenie

<div class="duo"><div>

### Drabina modeli z bramką jakości
<div class="card">
<div class="step">Kreuzberg / Tesseract: lokalnie, 0 zł</div>
<div class="step gate">bramka jakości odrzuca? ↓</div>
<div class="step">mistral-small → naprawa</div>
<div class="step gate">nadal źle? ↓</div>
<div class="step">mistral-large → naprawa</div>
</div>
<p>Droższy model tylko wtedy, gdy kod odrzuci tańszy wynik: <b>~2,4 centa</b> na formularz, #9 w <b>~40 s</b>.</p>

</div><div>

### Air gap i prompty w plikach
<div class="card">

```bash
LLM_PROVIDER=local
LLM_BASE_URL=http://vllm.urzad:8000/v1
```

```text
coi/prompts/field_extraction.md
coi/prompts/vision_page.md
coi/parsing/ladder.json
```

</div>
<p>Lokalny model bez ruchu wychodzącego, a reguły urzędu dopisuje się w plikach <code>.md</code>.</p>

</div></div>

---

# Liczby

<div class="nums">
<div><span class="big">22 → 12</span>rozbieżności krytycznych<br/>EVAL-3 → EVAL-5</div>
<div><span class="big">33/33</span>poprawnych JSON-ów<br/>(11 plików × 3 przebiegi)</div>
<div><span class="big">~40 s</span>#9 stypendium<br/>(mediana)</div>
<div><span class="big">$0.27</span>komplet 11 formularzy</div>
</div>

<div class="src">Źródło: app/results/eval-5/README.md, app/results/README.md</div>

---

<!-- _class: hero -->
<!-- _paginate: false -->

# Chcesz zobaczyć?

<div class="mono">./run-them-all.sh</div>

<div class="links">
Frontend&nbsp;&nbsp;http://localhost:8080<br/>
Swagger&nbsp;&nbsp;&nbsp;http://localhost:8000/docs
</div>
