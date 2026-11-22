import { useEffect, useState } from 'react'
import { ArrowLeft, BookMarked, Check, ChevronRight, Lock, Pencil, Plus, Search, Trash2, X } from 'lucide-react'
import { toast } from 'sonner'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { toastError } from '@/components/Notice'
import { api, type DictInfo, type DictItem } from '@/lib/api'
import { dictMsg } from '@/lib/messages'
import { plural } from '@/lib/plural'

const PAGE = 50
const TECH = /^[A-Za-z][A-Za-z0-9_]{0,63}$/ // DictionaryIn.id in backend/coi/dictionaries/api.py
// "Rodzaj zabudowy" -> "RodzajZabudowy": the dictionaryName a form JSON will reference
const techName = (s: string) => s.replace(/ł/g, 'l').replace(/Ł/g, 'L').normalize('NFD').replace(/[^A-Za-z0-9\s]/g, ' ')
  .split(/\s+/).filter(Boolean).map((w) => w[0].toUpperCase() + w.slice(1)).join('').replace(/^[0-9]+/, '').slice(0, 64)
const newId = () => `u${Date.now().toString(36)}`

const OriginBadge = ({ d }: { d: DictInfo }) => d.protected
  ? <Badge variant="secondary" className="gap-1"><Lock className="size-3" aria-hidden />z materiałów</Badge>
  : <Badge variant="outline">nasz</Badge>

export function DictionaryList({ onOpen }: { onOpen: (id: string) => void }) {
  const [items, setItems] = useState<DictInfo[] | null>(null)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  useEffect(() => { api.dictionaries().then(setItems).catch((e) => setError(dictMsg(e).title)) }, [])

  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Słowniki</h1>
          <p className="text-sm text-muted-foreground">Listy wartości dla pól wyboru. Słowniki z materiałów zadania są chronione przed usunięciem.</p>
        </div>
        <Button onClick={() => setCreating(true)}><Plus />Nowy słownik</Button>
      </div>
      {error && <p role="alert" className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</p>}
      {!items && !error && <p className="text-sm text-muted-foreground" aria-live="polite">Wczytuję słowniki…</p>}
      {items && (
        <div className="overflow-hidden rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/60 hover:bg-muted/60">
                <TableHead className="pl-4">Nazwa</TableHead>
                <TableHead className="hidden sm:table-cell">Nazwa techniczna</TableHead>
                <TableHead className="text-right">Pozycje</TableHead>
                <TableHead className="pr-4">Pochodzenie</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((d) => (
                <TableRow key={d.id} data-testid="dictionary-row" className="cursor-pointer" onClick={() => onOpen(d.id)}>
                  <TableCell className="py-3 pl-4 whitespace-normal">
                    <button type="button" className="flex items-center gap-2 text-left font-medium hover:underline focus-visible:underline" onClick={(e) => { e.stopPropagation(); onOpen(d.id) }}>
                      <BookMarked className="size-4 shrink-0 text-muted-foreground" aria-hidden />{d.name}
                    </button>
                  </TableCell>
                  <TableCell className="hidden font-mono text-xs text-muted-foreground sm:table-cell">{d.id}</TableCell>
                  <TableCell className="text-right text-sm tabular-nums">{(d.items ?? 0).toLocaleString('pl-PL')}</TableCell>
                  <TableCell className="pr-4"><OriginBadge d={d} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <NewDictionaryDialog open={creating} onOpenChange={setCreating} onCreated={onOpen} />
    </section>
  )
}

function NewDictionaryDialog({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (v: boolean) => void; onCreated: (id: string) => void }) {
  const [name, setName] = useState('')
  const [id, setId] = useState('')
  const [touched, setTouched] = useState(false) // technical name follows the name until edited by hand
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean)
  const tech = touched ? id : techName(name)
  const techOk = TECH.test(tech)

  async function save() {
    setBusy(true)
    try {
      const d = await api.newDictionary({ id: tech, name: name.trim(), items: lines.map((l, i) => ({ id: String(i + 1), name: l })) })
      toast.success(`Utworzono słownik „${d.name}”`)
      onOpenChange(false)
      setName(''); setId(''); setTouched(false); setText('')
      onCreated(d.id)
    } catch (e) {
      toastError(dictMsg(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !busy && onOpenChange(v)}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Nowy słownik</DialogTitle>
          <DialogDescription>Nazwa techniczna trafia do JSON formularza jako dictionaryName.</DialogDescription>
        </DialogHeader>
        <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); save() }}>
          <div className="grid gap-1.5">
            <Label htmlFor="dict-name">Nazwa</Label>
            <Input id="dict-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="np. Rodzaj zabudowy" maxLength={200} required />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="dict-id">Nazwa techniczna</Label>
            <Input id="dict-id" className="font-mono" value={tech} onChange={(e) => { setTouched(true); setId(e.target.value) }} aria-invalid={!!tech && !techOk} aria-describedby="dict-id-hint" />
            <p id="dict-id-hint" className={`text-xs ${tech && !techOk ? 'text-destructive' : 'text-muted-foreground'}`}>Litera na początku, potem litery, cyfry lub _ (bez polskich znaków i spacji), do 64 znaków.</p>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="dict-items">Pozycje, po jednej w wierszu</Label>
            <Textarea id="dict-items" rows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder={'jednorodzinna\nwielorodzinna\nzagrodowa'} />
            <p className="text-xs text-muted-foreground">{plural(lines.length, 'pozycja', 'pozycje', 'pozycji')}; puste wiersze pomijamy.</p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={busy} onClick={() => onOpenChange(false)}>Anuluj</Button>
            <Button type="submit" disabled={busy || !name.trim() || !techOk}>{busy ? 'Zapisuję…' : 'Utwórz słownik'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function DictionaryView({ id, onBack }: { id: string; onBack: () => void }) {
  const [dict, setDict] = useState<DictInfo | null>(null)
  const [items, setItems] = useState<DictItem[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('') // debounced q
  const [offset, setOffset] = useState(0)
  const [trail, setTrail] = useState<DictItem[]>([]) // opened tree branch, root first
  const [tick, setTick] = useState(0)
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null)
  const [adding, setAdding] = useState('')
  const [title, setTitle] = useState<string | null>(null)
  const [doomed, setDoomed] = useState(false)
  const [busy, setBusy] = useState(false)
  const parent = trail.at(-1)
  const levels = dict?.levels ?? []
  const level = levels[trail.length] ?? 'pozycja'

  useEffect(() => { const t = setTimeout(() => { setQuery(q.trim()); setOffset(0) }, 250); return () => clearTimeout(t) }, [q])
  useEffect(() => {
    let live = true
    api.dictionary(id, { q: query, parent: parent?.id, limit: PAGE, offset })
      .then((r) => { if (live) { setDict(r.dictionary); setItems(r.items); setTotal(r.total); setError('') } })
      .catch((e) => live && setError(dictMsg(e).title))
    return () => { live = false }
  }, [id, query, parent?.id, offset, tick])

  async function run(f: () => Promise<unknown>, ok: string) {
    setBusy(true)
    try { await f(); toast.success(ok); setTick((t) => t + 1); return true } catch (e) { toastError(dictMsg(e)); return false } finally { setBusy(false) }
  }
  const open = (path: DictItem[]) => { setTrail(path); setOffset(0); setQ(''); setQuery('') }

  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
      <Button variant="ghost" size="sm" onClick={onBack} className="mb-3"><ArrowLeft />Słowniki</Button>
      {error && <p role="alert" className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</p>}
      {dict && (
        <>
          <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              {title === null ? (
                <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
                  {dict.name}
                  <Button variant="ghost" size="icon-sm" aria-label="Zmień nazwę słownika" onClick={() => setTitle(dict.name)}><Pencil /></Button>
                </h1>
              ) : (
                <form className="flex items-center gap-2" onSubmit={async (e) => { e.preventDefault(); if (await run(() => api.renameDictionary(id, title.trim()), 'Zmieniono nazwę słownika')) setTitle(null) }}>
                  <Input aria-label="Nazwa słownika" className="h-9 w-80 max-w-full text-lg" value={title} maxLength={200} autoFocus onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === 'Escape' && setTitle(null)} />
                  <Button type="submit" size="sm" disabled={busy || !title.trim()}><Check />Zapisz</Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setTitle(null)}>Anuluj</Button>
                </form>
              )}
              <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span className="font-mono text-xs">{dict.id}</span><OriginBadge d={dict} />
                {levels.length > 1 && <span>Poziomy: {levels.join(' → ')}</span>}
              </p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <Button variant="outline" size="sm" className="text-destructive" disabled={dict.protected} onClick={() => setDoomed(true)} aria-describedby={dict.protected ? 'protected-why' : undefined}>
                <Trash2 />Usuń słownik
              </Button>
              {dict.protected && <p id="protected-why" className="max-w-64 text-right text-xs text-muted-foreground">Słownik z materiałów zadania: korzystają z niego formularze, więc nie można go usunąć.</p>}
            </div>
          </div>

          <div className="mb-3 flex flex-wrap items-center gap-3">
            <div className="relative w-full max-w-sm">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input type="search" aria-label="Szukaj pozycji" placeholder={trail.length ? `Szukaj w „${parent!.name}”` : 'Szukaj w całym słowniku'} className="pl-8" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            {levels.length > 1 && (
              <nav aria-label="Poziom drzewa" className="flex flex-wrap items-center gap-1 text-sm">
                <button type="button" className="hover:underline" onClick={() => open([])}>{levels[0]}: wszystkie</button>
                {trail.map((t, i) => (
                  <span key={t.id} className="flex items-center gap-1"><ChevronRight className="size-3.5 text-muted-foreground" aria-hidden />
                    <button type="button" className={i === trail.length - 1 ? 'font-medium' : 'hover:underline'} onClick={() => open(trail.slice(0, i + 1))}>{t.name}</button>
                  </span>
                ))}
              </nav>
            )}
          </div>

          <div className="overflow-hidden rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/60 hover:bg-muted/60">
                  <TableHead className="pl-4">{query ? 'Wyniki wyszukiwania' : level[0].toUpperCase() + level.slice(1)}</TableHead>
                  <TableHead className="w-40"><span className="sr-only">Akcje</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((it) => (
                  <TableRow key={it.id} data-testid="item-row">
                    <TableCell className="py-2 pl-4 whitespace-normal">
                      {editing?.id === it.id ? (
                        <form className="flex items-center gap-2" onSubmit={async (e) => { e.preventDefault(); if (await run(() => api.renameItem(id, it.id, editing.name.trim()), 'Zapisano pozycję')) setEditing(null) }}>
                          <Input aria-label="Nazwa pozycji" className="h-8" value={editing.name} maxLength={500} autoFocus onChange={(e) => setEditing({ id: it.id, name: e.target.value })} onKeyDown={(e) => e.key === 'Escape' && setEditing(null)} />
                          <Button type="submit" size="icon-sm" aria-label="Zapisz pozycję" disabled={busy || !editing.name.trim()}><Check /></Button>
                          <Button type="button" size="icon-sm" variant="ghost" aria-label="Anuluj edycję" onClick={() => setEditing(null)}><X /></Button>
                        </form>
                      ) : (
                        <>
                          <span>{it.name}</span>
                          {it.value && <span className="ml-2 font-mono text-xs text-muted-foreground">{it.value}</span>}
                          {!!it.path?.length && <p className="text-xs text-muted-foreground">{it.path.join(' › ')}</p>}
                        </>
                      )}
                    </TableCell>
                    <TableCell className="pr-3 text-right whitespace-nowrap">
                      {!query && it.level < levels.length && (
                        <Button variant="ghost" size="sm" onClick={() => open([...trail, it])} aria-label={`${levels[it.level]}: ${it.name}`}>{levels[it.level]}<ChevronRight /></Button>
                      )}
                      <Button variant="ghost" size="icon-sm" aria-label={`Edytuj ${it.name}`} onClick={() => setEditing({ id: it.id, name: it.name })}><Pencil /></Button>
                      <Button variant="ghost" size="icon-sm" aria-label={`Usuń ${it.name}`} disabled={busy} onClick={() => run(() => api.removeItem(id, it.id), `Usunięto „${it.name}”`)}><Trash2 /></Button>
                    </TableCell>
                  </TableRow>
                ))}
                {!items.length && (
                  <TableRow><TableCell colSpan={2} className="py-6 text-center text-sm text-muted-foreground">{query ? 'Nic nie pasuje do wyszukiwania.' : 'Brak pozycji.'}</TableCell></TableRow>
                )}
                {!query && (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={2} className="py-2 pl-4">
                      <form className="flex items-center gap-2" onSubmit={async (e) => { e.preventDefault(); if (await run(() => api.addItem(id, { id: newId(), name: adding.trim(), parent: parent?.id }), `Dodano „${adding.trim()}”`)) setAdding('') }}>
                        <Input aria-label="Nowa pozycja" className="h-8 max-w-md" placeholder={`Nowa pozycja${parent ? ` w „${parent.name}”` : ''}`} value={adding} maxLength={500} onChange={(e) => setAdding(e.target.value)} />
                        <Button type="submit" size="sm" variant="outline" disabled={busy || !adding.trim()}><Plus />Dodaj</Button>
                      </form>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          <div className="mt-3 flex items-center justify-between gap-3 text-sm text-muted-foreground">
            <span aria-live="polite">{total ? `${(offset + 1).toLocaleString('pl-PL')}–${Math.min(offset + PAGE, total).toLocaleString('pl-PL')} z ${total.toLocaleString('pl-PL')}` : ''}</span>
            <span className="flex gap-2">
              <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Poprzednie</Button>
              <Button variant="outline" size="sm" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>Następne</Button>
            </span>
          </div>
        </>
      )}

      <AlertDialog open={doomed} onOpenChange={(v) => !v && !busy && setDoomed(false)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Usunąć słownik?</AlertDialogTitle>
            <AlertDialogDescription>
              „{dict?.name}” zniknie razem ze wszystkimi pozycjami. Formularze, które go używają, stracą listę wartości. Tego nie da się cofnąć.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Anuluj</AlertDialogCancel>
            <AlertDialogAction variant="destructive" className="bg-destructive text-white hover:bg-destructive/90" disabled={busy}
              onClick={async (e) => { e.preventDefault(); if (await run(() => api.removeDictionary(id), `Usunięto słownik „${dict?.name}”`)) { setDoomed(false); onBack() } }}>
              {busy ? 'Usuwam…' : 'Usuń słownik'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
