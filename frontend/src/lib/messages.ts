import { ApiError, type Info } from './api'

// Every review note and error shown to the clerk: a short title, one sentence why, and what to do.
// The backend sends free text (needs_review.why, validator messages) and sometimes a `code`; we match on code first, then on wording.
// Unknown text falls back to a generic message that keeps the original, so nothing is ever hidden.
export type Msg = { title: string; why: string; action: string; original?: string }

type Rule = [RegExp, (m: RegExpMatchArray) => Omit<Msg, 'original'>]
const match = (rules: Rule[], s: string, fallback: Omit<Msg, 'original'>): Msg => {
  for (const [re, f] of rules) { const m = s.match(re); if (m) return { ...f(m), original: s } }
  return { ...fallback, original: s }
}

// needs_review.why from extraction/postprocess/build (backend/coi); quotes from the document are kept via capture groups.
const REVIEW: Rule[] = [
  [/pytanie sterujące odtworzone/i, () => ({ title: 'Pytanie dodane przez system', why: 'W dokumencie nie było tego pytania wprost: odtworzyliśmy je z warunków zgód lub sekcji, które od niego zależą.', action: 'Zmień etykietę na pytanie do obywatela, np. „Czy wniosek składa pełnomocnik?”, i sprawdź opcje.' })],
  [/etykieta źródłowa bez słów/i, () => ({ title: 'Pole bez opisu w dokumencie', why: 'W źródle przy tym polu nie ma słów, więc etykieta jest zgadywana.', action: 'Wpisz etykietę, która mówi obywatelowi, co wpisać, albo usuń pole.' })],
  [/model oznaczył pole jako opcjonalne/i, () => ({ title: 'Czy to pole jest wymagane?', why: 'Model uznał je za opcjonalne, ale dokument tego nie zaznacza, więc zostało wymagane.', action: 'Wyłącz „Wymagane”, jeśli obywatel może je pominąć; inaczej zaakceptuj.' })],
  [/źródło opisuje pole warunkiem/i, () => ({ title: 'Brakuje warunku wyświetlania', why: 'Dokument mówi „jeśli…” albo „w przypadku…”, a pole pokazuje się zawsze.', action: 'Kliknij ikonę warunku przy polu i wybierz, od której odpowiedzi zależy.' })],
  [/pole leży w bloku wyboru, ale nie ma warunku/i, () => ({ title: 'Brakuje warunku wyświetlania', why: 'Pole stoi pod pytaniem wyboru, ale pokazuje się niezależnie od odpowiedzi.', action: 'Kliknij ikonę warunku przy polu i wskaż odpowiedź, po której ma się pojawić.' })],
  [/warunek wyświetlania wskazywał nieistniejące pole/i, () => ({ title: 'Warunek dopasowany automatycznie', why: 'Warunek z dokumentu wskazywał pole, którego nie ma; dobraliśmy najbliższe po opcjach.', action: 'Otwórz warunek i sprawdź, czy zależy od właściwego pytania.' })],
  [/warunek wyświetlania wskazuje nieistniejące pole albo opcję/i, () => ({ title: 'Warunek wskazuje nieistniejące pole', why: 'Pole albo opcja, od której zależy warunek, zniknęła z formularza.', action: 'Otwórz warunek i wybierz pole oraz opcję z listy albo usuń warunek.' })],
  [/warunek z (?:papieru|treści) \(„(.+?)”/i, (m) => ({ title: 'Warunek dodany z treści dokumentu', why: `Z fragmentu „${m[1]}” wywnioskowaliśmy, kiedy pole ma się pokazać.`, action: 'Otwórz warunek i sprawdź, czy pytanie i odpowiedź się zgadzają.' })],
  [/wybór „(.+?)” z papieru odtworzony jako pole/i, (m) => ({ title: 'Pytanie wyboru dodane przez system', why: `Na papierze było „${m[1]}” do skreślenia; zamieniliśmy to na pytanie z opcjami.`, action: 'Zmień etykietę na pytanie do obywatela, np. „Czego dotyczy wniosek?”, i sprawdź opcje.' })],
  [/opcje odtworzone z papieru/i, () => ({ title: 'Opcje do sprawdzenia', why: 'Opcje odczytaliśmy z papierowego formularza i mogą mieć inne brzmienie.', action: 'Porównaj opcje z dokumentem i popraw ich treść.' })],
  [/pole wyboru ma mniej niż 2 opcje/i, () => ({ title: 'Za mało opcji', why: 'Pole wyboru ma mniej niż dwie opcje, więc obywatel nie ma z czego wybrać.', action: 'Kliknij „Dodaj opcję” albo zmień pole na zwykłe pole tekstowe.' })],
  [/propozycja słownika (.+)$/i, (m) => ({ title: 'Proponowany słownik', why: `Opcje tego pola pasują do słownika „${m[1]}”.`, action: 'Przyjmij słownik w „Cały formularz” albo zaakceptuj pole bez zmian.' })],
  [/pole spoza adresu przeniesione z sekcji adresu składającego do „(.+?)”/i, (m) => ({ title: 'Pole przeniesione', why: `Pole nie dotyczyło adresu, więc przenieśliśmy je do „${m[1]}”.`, action: 'Sprawdź, czy stoi we właściwej sekcji; w razie potrzeby przesuń je strzałkami.' })],
  [/wygląda na dane wnioskodawcy lub pełnomocnika/i, () => ({ title: 'Możliwy duplikat danych wnioskodawcy', why: 'Te dane zbiera już stały szablon (wnioskodawca, pełnomocnik).', action: 'Usuń pole, jeśli powtarza dane z szablonu; jeśli dotyczy przedmiotu wniosku, zaakceptuj.' })],
  [/załącznik „dla każdego” elementu leży poza sekcją powtarzalną/i, () => ({ title: 'Załącznik poza sekcją powtarzalną', why: 'Dokument wymaga załącznika dla każdej pozycji, a pole jest tylko jedno.', action: 'Przenieś pole do sekcji powtarzalnej albo zaakceptuj, jeśli wystarczy jeden plik.' })],
  [/etykiety pola nie ma w dokumencie/i, () => ({ title: 'Etykieta nie pochodzi z dokumentu', why: 'Przy miejscu do wpisania w źródle jest inny tekst niż etykieta pola.', action: 'Porównaj z dokumentem i popraw etykietę.' })],
  [/miejsce do wpisania bez pola|brak pola dla(.*)/i, (m) => ({ title: 'Możliwe brakujące pole', why: `W dokumencie jest miejsce do wpisania${m[1] ? ` (${m[1].trim()})` : ''}, którego nie ma w formularzu.`, action: 'Dodaj pole w odpowiedniej sekcji przyciskiem „Dodaj pole” albo zaakceptuj, jeśli jest zbędne.' })],
  [/blok z miejscem do wpisania usunięty jako szablon/i, () => ({ title: 'Usunięty fragment do sprawdzenia', why: 'Fragment z miejscem do wpisania uznaliśmy za część szablonu i pominęliśmy.', action: 'Jeśli w szablonie tego nie ma, dodaj pole ręcznie; inaczej zaakceptuj.' })],
  [/załącznik z listy bez pola do wgrania/i, () => ({ title: 'Załącznik bez pola na plik', why: 'Dokument wymienia załącznik, a formularz nie pozwala go dodać.', action: 'Dodaj pole typu „Plik” w sekcji załączników.' })],
  [/wynik niepewny: bramka jakości/i, () => ({ title: 'Wynik wymaga dokładnego przejrzenia', why: 'Automatyczna kontrola jakości nie przeszła; szczegóły są poniżej.', action: 'Przejrzyj wszystkie strony z czerwoną kropką i porównaj z dokumentem.' })],
  [/tytuł pusty albo dłuższy niż 255/i, () => ({ title: 'Tytuł do poprawy', why: 'Tytuł jest pusty albo ma ponad 255 znaków.', action: 'Wpisz tytuł do 255 znaków, np. „Wniosek o wydanie…”.' })],
  [/tytuł nie zaczyna się od (.+)$/i, (m) => ({ title: 'Tytuł nie wygląda na nazwę wniosku', why: `Tytuły COI zaczynają się od: ${m[1]}.`, action: 'Zmień tytuł, np. na „Wniosek o …”.' })],
  [/brak adresata/i, () => ({ title: 'Brak adresata', why: 'Nie wiemy, do którego urzędu trafia wniosek.', action: 'Uzupełnij nazwę urzędu w polu adresata.' })],
  [/opłata za pełnomocnictwo nie jest opłatą za sprawę/i, () => ({ title: 'Pominięta opłata', why: 'Opłata za pełnomocnictwo nie jest opłatą za sprawę, więc jej nie dodaliśmy.', action: 'Nic nie trzeba zmieniać; zaakceptuj.' })],
  [/opłata za sprawę bez oparcia/i, () => ({ title: 'Pominięta opłata za sprawę', why: 'Model podał opłatę, której nie ma we wskazanym fragmencie dokumentu.', action: 'Sprawdź w dokumencie, czy jest opłata; zaakceptuj, jeśli jej nie ma.' })],
  [/wymóg odpisu z rejestru/i, () => ({ title: 'Pominięty odpis z rejestru', why: 'Model zgłosił wymóg odpisu, ale wskazany fragment go nie zawiera.', action: 'Sprawdź w dokumencie; jeśli odpis jest wymagany, dodaj pole „Plik”.' })],
  [/składa się tylko osobiście/i, () => ({ title: 'Sposób składania do sprawdzenia', why: 'Model uznał, że wniosek składa się tylko osobiście, ale fragment tego nie mówi.', action: 'Sprawdź przełącznik „tylko osobiście” w „Cały formularz”.' })],
  [/„(.+?)”: kilka warunków zgody/i, (m) => ({ title: 'Kilka warunków jednej zgody', why: `Zgoda „${m[1]}” miała kilka warunków; został tylko ostatni.`, action: 'Otwórz warunek zgody i sprawdź, czy jest właściwy.' })],
  [/zgód innej osoby niż wnioskodawca zamieniono/i, () => ({ title: 'Zgody zamienione na oświadczenia', why: 'Zgody innych osób zbieramy jako pliki „Oświadczenie…”, bo podpisuje je kto inny.', action: 'Sprawdź pola „Oświadczenie…” w sekcji załączników.' })],
  [/zgoda na przetwarzanie danych osobowych z dokumentu usunięta/i, () => ({ title: 'Zgoda RODO usunięta', why: 'Ta zgoda jest już w stałym szablonie formularza.', action: 'Nic nie trzeba zmieniać; zaakceptuj.' })],
  [/treść zgody do redakcji/i, () => ({ title: 'Treść zgody do zredagowania', why: 'Zgoda ma formy typu „wyrażam/am”, a COI wymaga czasu teraźniejszego i neutralnej formy.', action: 'Przeredaguj treść, np. „Wyrażam zgodę…” bez form żeńskich i męskich.' })],
  [/Tę część warunku pominięto/i, () => ({ title: 'Część warunku pominięta', why: 'Fragmentu warunku nie dało się zapisać, więc element nie jest już wymagany.', action: 'Otwórz warunek, uzupełnij go i włącz „Wymagane”, jeśli trzeba.' })],
]
export const reviewMsg = (why: string): Msg =>
  match(REVIEW, why, { title: 'Do sprawdzenia', why, action: 'Porównaj pole z dokumentem: popraw je albo kliknij „Akceptuję bez zmian”.' })

// Validator errors from PUT /forms/{id} (backend/coi/generator/validate.py): {rule, path, message}.
type VErr = { path?: string; message?: string; rule?: string }
const tech = (s = '') => s.match(/'([^']+)'/)?.[1] ?? ''
export function validationMsg(e: VErr): Msg {
  const m = e.message ?? ''
  const t = tech(m)
  const f = t ? `„${t}”` : 'to pole'
  const by: Record<string, Omit<Msg, 'original'>> = {
    title: { title: 'Tytuł formularza', why: 'Tytuł jest pusty albo ma ponad 255 znaków.', action: 'Wpisz tytuł do 255 znaków w „Cały formularz”.' },
    R1: { title: 'Układ stron', why: 'Formularz potrzebuje co najmniej jednej strony z polami i strony końcowej.', action: 'Nie usuwaj ostatnich stron; zaimportuj plik ponownie, jeśli układ się rozpadł.' },
    R2: /no fields/.test(m) ? { title: 'Pusta strona', why: 'Każda strona musi mieć co najmniej jedno pole.', action: 'Dodaj sekcję i pole na tej stronie.' }
      : /nested/.test(m) ? { title: 'Sekcja w sekcji', why: 'COI nie pozwala zagnieżdżać sekcji.', action: `Przenieś pola z ${f} do sekcji nadrzędnej i usuń zagnieżdżoną.` }
      : { title: 'Pole poza sekcją', why: 'Każde pole musi leżeć w sekcji.', action: `Usuń ${f} i dodaj je ponownie w sekcji („Dodaj pole”).` },
    R3: { title: 'Pole na stronie końcowej', why: 'Na stronie końcowej mogą być tylko informacje, bez pól do wypełnienia.', action: `Usuń ${f} albo dodaj je na wcześniejszej stronie.` },
    R4: { title: 'Błędna walidacja pola', why: 'Ustawienia walidacji pola są uszkodzone.', action: `Przełącz „Wymagane” przy ${f} dwa razy, żeby je odtworzyć.` },
    R5: { title: 'Strony nie są połączone', why: 'Przejścia między stronami nie obejmują wszystkich stron.', action: 'Zaimportuj plik ponownie; ręczna edycja tego nie naprawi.' },
    R6: /compares with '([^']*)'/.test(m)
      ? { title: 'Warunek z nieistniejącą opcją', why: `Warunek porównuje z „${m.match(/compares with '([^']*)'/)![1]}”, a takiej opcji już nie ma.`, action: 'Otwórz warunek przy polu i wybierz opcję z listy.' }
      : { title: 'Warunek wskazuje usunięte pole', why: 'Pole, od którego zależy warunek, zostało usunięte lub przemianowane.', action: 'Otwórz warunek przy polu i wybierz pole z listy albo usuń warunek; możesz też cofnąć usunięcie.' },
    date: { title: 'Zła data domyślna', why: 'Domyślna wartość daty musi mieć postać RRRR-MM-DD.', action: `Popraw domyślną datę w ${f} albo ją usuń.` },
    readOnly: { title: 'Wymagane pole tylko do odczytu', why: 'Obywatel nie może go wypełnić, więc wniosku nie da się wysłać.', action: `Wyłącz „Wymagane” przy ${f}.` },
    choice: /both/.test(m)
      ? { title: 'Słownik i opcje naraz', why: 'Pole wyboru ma jednocześnie słownik i własne opcje.', action: `Zostaw w ${f} tylko słownik albo tylko opcje.` }
      : { title: 'Pole wyboru bez opcji', why: 'Pole wyboru nie ma ani opcji, ani słownika.', action: `Dodaj opcje w ${f} („Dodaj opcję”).` },
    techName: { title: 'Powtórzona nazwa techniczna', why: `Nazwa techniczna ${f} występuje więcej niż raz.`, action: 'Usuń zdublowane pole albo zmień etykietę jednego z nich i dodaj je ponownie.' },
    schema: { title: 'Niepoprawna wartość pola', why: 'Jedno z ustawień ma zły format dla COI.', action: 'Cofnij ostatnią zmianę w tym polu albo popraw jego treść.' },
    structure: { title: 'Uszkodzona struktura', why: 'JSON formularza ma nieoczekiwany kształt.', action: 'Pobierz JSON i zgłoś problem; możesz też zaimportować plik ponownie.' },
  }
  return { ...(by[e.rule ?? ''] ?? { title: 'Błąd w formularzu', why: m || 'Walidator odrzucił formularz.', action: 'Popraw wskazane pole i zapisz ponownie.' }), original: [e.path, m].filter(Boolean).join(' ') }
}

// API errors (RFC 9457 problem+json from backend/coi/api.py and nginx): status + code, then wording.
export function apiMsg(e: unknown, info?: Info | null): Msg {
  if (!(e instanceof ApiError)) {
    const s = e instanceof Error ? e.message : String(e)
    return /fetch|network|Failed/i.test(s)
      ? { title: 'Brak połączenia z serwerem', why: 'Przeglądarka nie dostała odpowiedzi.', action: 'Sprawdź połączenie i spróbuj ponownie za chwilę.', original: s }
      : { title: 'Coś poszło nie tak', why: s, action: 'Spróbuj ponownie; jeśli błąd wraca, odśwież stronę.', original: s }
  }
  const l = info?.limits
  const s = e.message
  const by: Record<number, Omit<Msg, 'original'>> = {
    400: e.code === 'invalid_filename' || /file name/i.test(s)
      ? { title: 'Niedozwolona nazwa pliku', why: 'Nazwa jest za długa albo ma znaki, których serwer nie przyjmuje.', action: `Skróć nazwę pliku do ${l?.max_filename_len ?? 250} znaków${l ? ` i usuń znaki ${l.forbidden_filename_chars}` : ' i usuń znaki specjalne'}, potem wczytaj go ponownie.` }
      : { title: 'Serwer odrzucił żądanie', why: 'Wysłane dane są niekompletne.', action: 'Wczytaj jeden plik naraz i spróbuj ponownie.' },
    401: { title: 'Sesja wygasła', why: 'Token dostępu jest nieważny albo wygasł.', action: 'Kliknij „Token” w nagłówku i wklej nowy token.' },
    404: { title: 'Nie ma takiego projektu', why: 'Projekt mógł zostać usunięty.', action: 'Wróć do listy projektów i odśwież ją.' },
    409: { title: 'Projekt za stary na przebudowę', why: 'Ten projekt powstał przed funkcją przebudowy.', action: 'Zaimportuj plik ponownie, żeby móc go przebudować.' },
    413: { title: 'Plik jest za duży', why: `Serwer przyjmuje pliki do ${l?.max_file_mb ?? '?'} MB.`, action: 'Zmniejsz plik (np. zapisz PDF w niższej jakości) albo podziel go i wczytaj ponownie.' },
    415: { title: 'Nieobsługiwany typ pliku', why: 'Rozszerzenie nie zgadza się z zawartością albo typ nie jest obsługiwany.', action: `Wczytaj plik ${l ? l.extensions.map((x) => x.toUpperCase()).join(', ') : 'PDF lub DOCX'} z poprawnym rozszerzeniem.` },
    422: e.code === 'invalid_form'
      ? { title: 'Formularz ma błędy', why: 'Zmiany nie zostały zapisane, bo walidator COI je odrzucił.', action: 'Popraw pola wskazane na liście i zapisz ponownie.' }
      : { title: 'Nie da się odczytać pliku', why: 'Plik jest uszkodzony, zaszyfrowany albo nie zawiera formularza.', action: 'Otwórz go u siebie, zapisz ponownie jako PDF i wczytaj jeszcze raz.' },
    502: { title: 'Błąd modelu językowego', why: 'Usługa AI zwróciła błąd podczas odczytu pól.', action: 'Wczytaj plik ponownie za kilka minut.' },
    504: { title: 'Przekroczony czas', why: 'Odczyt trwał dłużej, niż pozwala serwer.', action: 'Wczytaj plik ponownie; przy dużych plikach podziel je na mniejsze.' },
  }
  return { ...(by[e.status] ?? { title: `Błąd serwera (${e.status})`, why: s, action: 'Spróbuj ponownie za chwilę.' }), original: s }
}

// JSONata problems from lib/condition.ts (check()).
const COND: Rule[] = [
  [/^Wyrażenie jest puste/, () => ({ title: 'Pusty warunek', why: 'Warunek nie ma treści.', action: 'W zakładce „Graficzny” wybierz pole i odpowiedź albo usuń warunek.' })],
  [/^Błąd składni/, () => ({ title: 'Błąd składni', why: 'Wyrażenia nie da się odczytać: zwykle brakuje nawiasu lub cudzysłowu.', action: 'Sprawdź miejsce wskazane obok albo zbuduj warunek w zakładce „Graficzny”.' })],
  [/^Nie ma takiego pola: (.+)\.$/, (m) => ({ title: 'Nieznane pole', why: `Warunek wskazuje ${m[1]}, którego nie ma w formularzu.`, action: 'Wybierz pole z listy w zakładce „Graficzny”.' })],
  [/^„(.+)” nie jest opcją pola (.+)\.$/, (m) => ({ title: 'Nieznana opcja', why: `„${m[1]}” nie jest odpowiedzią w polu ${m[2]}.`, action: 'Zaznacz opcję z listy w zakładce „Graficzny”.' })],
  [/sekcji powtarzalnej: (użyj .+)\.$/, (m) => ({ title: 'Zła ścieżka do sekcji powtarzalnej', why: 'Pola w sekcji powtarzalnej wymagają innej ścieżki.', action: `${m[1][0].toUpperCase()}${m[1].slice(1)}.` })],
  [/nie może zależeć od pola w jej środku/, () => ({ title: 'Zależność od sekcji powtarzalnej', why: 'Pole poza sekcją powtarzalną nie wie, którą jej kopię sprawdzić.', action: 'Uzależnij pole od pytania spoza sekcji powtarzalnej.' })],
  [/nie odwołuje się do żadnego pola/, () => ({ title: 'Warunek bez pola', why: 'Wyrażenie nie sprawdza żadnej odpowiedzi obywatela.', action: 'Wybierz pole i odpowiedź w zakładce „Graficzny”.' })],
]
export const conditionMsg = (s: string): Msg => match(COND, s, { title: 'Błąd warunku', why: s, action: 'Zbuduj warunek w zakładce „Graficzny”.' })

// Client-side checks before upload (lib/queue.ts check()) use the same wording as the API.
export const uploadMsg = (status: number, detail: string | undefined, info?: Info | null) =>
  apiMsg(new ApiError(status, detail ?? '', [], detail && /file name/i.test(detail) ? 'invalid_filename' : undefined), info)
