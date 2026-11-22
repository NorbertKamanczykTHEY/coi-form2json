# Materiały do oddania (pkt 4 treści zadania)

| Plik | Co to jest |
|---|---|
| [opis-projektu.md](opis-projektu.md) | Tytuł i szczegółowy opis projektu |
| [prezentacja.md](prezentacja.md) → [prezentacja.pdf](prezentacja.pdf) | 10 slajdów (Marp) |
| [wynikowe-json.md](wynikowe-json.md) | Wynikowe JSON-y #2, #3, #4, #6, #7, #8, #9 |
| `img/` | Zrzuty frontu, skopiowane z `frontend/e2e/screenshots/` |

Render PDF:

```bash
cd app/docs/submission
npx -y @marp-team/marp-cli@4.2.3 prezentacja.md --pdf --html --allow-local-files -o prezentacja.pdf
```

## Mapa liczb (do podmiany po kolejnym pomiarze)

Wszystkie liczby pochodzą z EVAL-5 na HEAD `718fa0d`: [results/eval-5/README.md](../../results/eval-5/README.md), [results/README.md](../../results/README.md), [results/eval-5/zmiennosc.md](../../results/eval-5/zmiennosc.md). Po nowym pomiarze wystarczy podmienić liczby w miejscach z tabeli i wyrenderować PDF:

| Liczba | Wartość teraz | Gdzie |
|---|---|---|
| Rozbieżności krytyczne EVAL-3 → 4 → 5 | 22 → 12 → 12 | opis „Jakość wyniku”, slajd 5 (M4), slajd 7 |
| Czas mediana #8 / #9 (z 3 przebiegów) i ile poniżej 60 s | 42.8 s (2/3) / 39.7 s (3/3) | opis „Koszt i czas”, slajd 7, slajd 10 |
| Tabela czasów, pól i kosztów | 7 wierszy | opis „Koszt i czas”, slajd 7, `wynikowe-json.md` (9 wierszy) |
| Koszt kompletu 11 plików (przebiegi mediany) | $0.27 ($0.2660), średnio 2,4 centa na plik | opis, slajd 7, slajd 9, slajd 10 |
| Bramka przeszła 3/3 | tylko #1 | opis „Ograniczenia”, slajd 8 |
| Warunki SHOW w wynikach | 382 | opis (rozszerzenie III), slajd 5 |
| Testy backendu | 302 | opis „Architektura”, slajd 8 |

Warunki SHOW policzone tak: `python3 -c "import json,glob;print(sum(json.dumps(json.load(open(f))).count('\"SHOW\"') for f in glob.glob('results/*.coi.json')))"` z katalogu `app/`. Testy: `cd backend && uv run pytest -m "not eden" -q`.
