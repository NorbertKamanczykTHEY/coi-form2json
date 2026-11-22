# Wymagania: „COI – Pełna treść zadania konkursowego”

Źródło: `materials/COI - Pełna treść zadania konkursowego.pdf`. Numeracja według dokumentu. Stan spełnienia z dowodami: [compliance.md](compliance.md). Kolumna „Gdzie” wskazuje moduł albo wątek, który za wymaganie odpowiada.

## 2. Wyzwanie
- AI analizuje formularze w różnych formatach i generuje dane w zdefiniowanej postaci ustrukturyzowanej.
- Kontekst docelowy: formularze mają być w przyszłości obsługiwane także przez agentów AI (Generator Formularzy, AI HUB, Multiportal).
- Użytkownicy: urzędnicy, którzy cyfryzują formularze e-usług.

## 3.2 Zakres minimalny (obowiązkowy)
| ID | Wymaganie | Gdzie |
|---|---|---|
| M1 | Usługa REST API przyjmuje plik formularza: PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG | API + parsowanie |
| M2 | Zwraca JSON odpowiadający zawartości formularza | ekstrakcja pól + generator |
| M3 | JSON jest zgodny ze strukturą oczekiwaną (schemat i wzorce #1, #5) | generator + walidator |
| M4 | JSON spełnia wymagania projektowania formularzy (np. strony tematyczne; Standardy, Reguły techniczne) | generator |
| M5 | Dokumentacja architektury rozwiązania | docs (do `app/`) |

## 3.3 Rozszerzenia (dodatkowe punkty)
| ID | Wymaganie | Gdzie |
|---|---|---|
| R-I | Słowniki i dane inicjalne powiązane z pasującymi polami | generator |
| R-II | Propozycja nowego słownika, jeśli brakuje go w bazie | generator + `/dictionaries` |
| R-III | Zależności i dynamiczne przepływy między polami, sekcjami i stronami (wybór użytkownika) | ekstrakcja + generator (JSONata) |
| R-IV | Prosty frontend: wczytanie plików i przegląd wynikowego JSON | frontend |
| R-V | Wizualizacja wynikowego JSON jako formularza e-usługi | frontend (podgląd) |
| R-VI | Walidacje danych (typ, długość, telefon, PESEL…) oraz UX (batch, makiety) | generator (walidatory) + frontend |

## 4. Wymagania formalne (oddanie)
- Szczegółowy opis i tytuł projektu.
- Prezentacja PDF, maksymalnie 10 slajdów.
- Wynikowe pliki JSON (dla #2, #3, #4, #7, #8, #9).
- Film do 3 minut w otwartym repozytorium (link).
- Repozytorium kodu.
- Opcjonalnie: zrzuty ekranu, link do demo, grafiki.

## 5. Wymagania techniczne
| ID | Wymaganie | Gdzie |
|---|---|---|
| T1 | Java 21+ albo Python 3.14+ (preferowane) | backend: Python 3.14 |
| T2 | Tylko open source bez copyleftu (AGPL, GPL), bez licencji komercyjnych, najnowsze stabilne wersje | wszystkie |
| T3 | Bez zewnętrznych API, MCP i SaaS. **Bez modeli LLM dostępnych wyłącznie przez API.** Wyjątek mentorów: Eden, modele z otwartymi wagami, konfigurowalny endpoint | `llm.py`, `LLM_BASE_URL` |
| T4 | REST API przyjmuje **jeden** plik blankietu | API |
| T5 | Tylko obsługiwane formaty, MIME musi się zgadzać z rozszerzeniem | parsowanie (`detect`) |
| T6 | Nazwa pliku ≤ 250 znaków, bez `; : > < / \ | ' * % $` | API |
| T7 | Maksymalny rozmiar pliku konfigurowalny parametrem aplikacji | API (`MAX_FILE_MB`) |
| T8 | Plik tylko w pamięci albo w katalogu tymczasowym na czas żądania | API + parsowanie |
| T9 | Kompletna konfiguracja Docker, środowisko odizolowane | każdy moduł |
| T10 | Obrazy: oficjalne, lekkie (Alpine), jawne wersje, bez `latest`, użytkownik bez roota, tylko potrzebne porty, sekrety w runtime | każdy Dockerfile |
| T11 | Konfiguracja: maksymalny rozmiar pliku, JWT, parametry integracji | `config.py`, `.env.example` |
| T12 | README.md: budowanie obrazu, uruchomienie, konfiguracja, opis REST API | `app/README.md` |

## 6. Testowanie
- Finaliści uruchamiają rozwiązanie na żywo na **nowych plikach** podanych podczas obrony. Potrzebny jest szybki i odporny przebieg na formularzach, których nie widzieliśmy.

## 8. Kryteria oceny
| Kryterium | Waga | Co je podnosi |
|---|---|---|
| Kompletność (minimum, potem I–V) | 30% | każdy próg z 3.3 |
| Intuicyjność | 20% | front, podgląd e-usługi, raport `needs_review` |
| Jakość kodu | 20% | kontrakty, testy, czytelna architektura |
| Potencjał wdrożeniowy (w tym koszt) | 20% | koszt na formularz, IdP/JWKS, Docker, audyt |
| Oryginalność | 10% | drabina eskalacji z bramką, edytor z mapą źródła |

Uwaga: w 3.3 pkt V to wizualizacja, a pkt VI to walidacje. W kryteriach „V” oznacza walidacje. Wizualizacja nie ma osobnego progu.
