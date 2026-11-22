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
  .trio { display: flex; gap: 22px; }
  .trio > div { flex: 1; }
  .trio h3 { color: #0b4f8a; font-size: 23px; margin: 0 0 8px; }
  .trio .shot { height: 300px; }
  .trio p { font-size: 19px; margin: 10px 0 0; line-height: 1.35; }
---

<!-- _class: hero -->
<!-- _paginate: false -->

# Blankiet → e-usługa

<p class="lead">Urzędy przepisują papierowe wnioski do e-usług ręcznie, pole po polu.<br/>U nas wrzucasz plik i zwykle w niecałą minutę masz gotową e-usługę.</p>

---

# Jak to działa

<div class="flow">
<div class="box"><b>📄</b>Word, PDF, Excel albo zdjęcie</div>
<div class="arrow">→</div>
<div class="box"><b>Czytamy</b>tekst na miejscu, bez wysyłania pliku</div>
<div class="arrow">→</div>
<div class="box"><b>Rozpoznajemy</b>pola wniosku z pomocą AI</div>
<div class="arrow">→</div>
<div class="box"><b>Budujemy</b>formularz według wzorców COI</div>
<div class="arrow">→</div>
<div class="box"><b>Sprawdzamy</b>z zasadami COI</div>
<div class="arrow">→</div>
<div class="end" style="white-space:nowrap">Gotowa<br/>e-usługa</div>
</div>

<p class="lead" style="margin-top:40px">Urzędnik dostaje gotowy formularz i krótką listę rzeczy do sprawdzenia.</p>

---

# Wrzucasz, sprawdzasz, oglądasz

<div class="trio">
<div><h3>Wiele plików naraz</h3><img class="shot" src="img/clean-import-log.png"/><p>Zamykasz okno, praca trwa dalej, każdy krok widać na liście.</p></div>
<div><h3>Na czerwono to, co sprawdzić</h3><img class="shot" src="img/clean-editor-note-1.png"/><p>Przy wątpliwym polu widać powód i co zrobić. Zostawiasz je albo poprawiasz.</p></div>
<div><h3>Tak zobaczy to mieszkaniec</h3><img class="shot" src="img/clean-mockup.png"/><p>Pola pojawiają się po wyborze odpowiedzi, imię i nazwisko z profilu.</p></div>
</div>

---

# Poprawiasz bez programisty

<div class="duo"><div>

### Poprawki prosto w podglądzie
<img class="shot" src="img/clean-condition-mark-1.png"/>
<p>Zmieniasz nazwy, pola obowiązkowe i warunki, opisane zwykłym zdaniem. Dodajesz i usuwasz pola.</p>

</div><div>

### Kiedy pokazać pole
<img class="shot" src="img/clean-condition-graphic.png" style="object-position: center"/>
<p>„Pokaż, gdy wnioskujesz w imieniu innej osoby” ustawiasz kliknięciami. Kraje i gminy wybiera się z gotowych list.</p>

</div></div>

---

# Szybko i tanio

<div class="duo" style="gap:40px; font-size:24px"><div style="flex:1.3">

- Tekst czytamy na miejscu, za darmo.
- AI tylko, gdy trzeba: najpierw mały, tani model, większy dopiero po pomyłce.
- Długi wniosek czytamy po stronach naraz: deklaracja śmieciowa z 3 min do 43 s.
- Pełny test (11 wniosków × 3) kosztował 81 centów.
- Może działać w sieci urzędu, bez wysyłania danych.

</div><div class="nums" style="flex:1; flex-direction:column; gap:12px; margin-top:0">
<div><span class="big">~10 gr</span>za formularz (2,4 centa)</div>
<div><span class="big">$0.27</span>za 11 formularzy</div>
<div><span class="big">~40 s</span>na duży wniosek</div>
</div></div>

<div class="src">Źródło: app/results/eval-5/README.md ($0.2660, test $0.8071, czasy 42.8 s i 39.7 s), app/docs/architecture.md (#8 w EVAL-3: 184.5 s; drabina modeli). 1 USD ≈ 4 zł.</div>

---

<!-- _class: hero -->
<!-- _paginate: false -->

# Chcesz zobaczyć?

<div class="mono">./run-them-all.sh</div>

<div class="links">
Aplikacja&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;http://localhost:8080<br/>
Dokumentacja&nbsp;&nbsp;&nbsp;http://localhost:8000/docs
</div>
