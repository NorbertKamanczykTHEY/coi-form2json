# 0010. Modele za adapterem dostawcy, tryb air gap
Data: 2026-11-21 · Status: przyjęta
Źródło: SPEC (T3) + MENTORZY + ZESPÓŁ

## Kontekst
- Wymóg T3: bez zewnętrznych API i SaaS, bez modeli LLM dostępnych wyłącznie przez API. Wyjątek od mentorów: Eden LLM, modele z otwartymi wagami, konfigurowalny endpoint.
- Nasz wybór: Eden to jedna implementacja dostawcy. Te same modele da się uruchomić lokalnie (vLLM, Ollama). Tryb air gap (zero ruchu wychodzącego) jest naszym wymogiem, nie zadania.

## Decyzja
- LLM i VLM są wołane wyłącznie przez adapter dostawcy (`llm.py`). Eden (`LLM_BASE_URL` = `https://api.edenai.run/v3`) to jedna implementacja, lokalny serwer drugą.
- **Przełączenie na lokalny serwer:** `LLM_BASE_URL` na adres serwera w sieci compose, nazwy modeli w `ladder.json` (`LADDER_PATH`), `LLM_API_KEY` pusty. Bez zmian w kodzie.
- **Offline działają:** wykrywanie typu, Kreuzberg + Tesseract, generator, walidator, SQLite, front. **Wymagają modelu:** VLM dla skanów, ekstrakcja pól, sędzia słowników.
- W air gap potrzebny jest lokalny serwer modeli z odpowiednikami modeli z `ladder.json`. JWT w tym trybie: HS256 albo JWKS z sieci wewnętrznej ([0015](0015-jwt-tylko-weryfikacja.md)).

## Konsekwencje
- Dokumenty opisują dziś klienta zgodnego z OpenAI (`base_url` + `model`). Dostawca z innym protokołem wymaga nowej implementacji adaptera.
- Jakość i czas lokalnych modeli nie są zmierzone ([0007](0007-t0-lokalnie-skany-do-vlm.md)). Bez VLM skany degradują się do Tesseract.
- README ma opisać przełączenie i tryb offline.
