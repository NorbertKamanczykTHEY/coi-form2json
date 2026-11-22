import { toastError } from '@/components/Notice'
import { apiMsg } from '@/lib/messages'
import { useState } from 'react'
import { BookMarked, CircleAlert, FileText, FileUp, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, type ListItem } from '@/lib/api'
import { plural } from '@/lib/plural'

const date = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })

export default function ProjectList({ items, fresh, error, onOpen, onImport, onChanged }: {
  items: ListItem[] | null; fresh: Set<string>; error: string; onOpen: (id: string) => void; onImport: () => void; onChanged: () => void
}) {
  const [doomed, setDoomed] = useState<ListItem | null>(null)
  const [busy, setBusy] = useState(false)

  async function remove() {
    if (!doomed) return
    setBusy(true)
    try {
      await api.remove(doomed.id)
      toast.success(`Usunięto projekt „${doomed.title || doomed.filename}”`)
      setDoomed(null)
      onChanged()
    } catch (e) {
      toastError(apiMsg(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Projekty</h1>
          <p className="text-sm text-muted-foreground">Formularze przeniesione z papieru. Otwórz projekt, żeby rozstrzygnąć uwagi i sprawdzić makietę.</p>
        </div>
      </div>

      {error && <p role="alert" className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</p>}

      {items && items.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed bg-card px-6 py-14 text-center">
          <FileUp className="size-8 text-primary" aria-hidden />
          <p className="font-medium">Nie ma jeszcze żadnego projektu</p>
          <p className="max-w-sm text-sm text-muted-foreground">Zaimportuj skan albo dokument formularza (PDF, DOCX, ODS, zdjęcie). Każdy plik stanie się projektem.</p>
          <Button onClick={onImport}>Importuj pliki</Button>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="overflow-hidden rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/60 hover:bg-muted/60">
                <TableHead className="w-[55%] pl-4">Formularz</TableHead>
                <TableHead className="hidden md:table-cell">Utworzono</TableHead>
                <TableHead>Uwagi do decyzji</TableHead>
                <TableHead className="hidden sm:table-cell">Słowniki</TableHead>
                <TableHead className="w-12"><span className="sr-only">Akcje</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((f) => (
                <TableRow key={f.id} data-testid="project-row" className="cursor-pointer" onClick={() => onOpen(f.id)}>
                  <TableCell className="max-w-0 py-3 pl-4 whitespace-normal">
                    <div className="flex items-start gap-3">
                      <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                      <div className="min-w-0">
                        <button type="button" className="text-left font-medium hover:underline focus-visible:underline" onClick={(e) => { e.stopPropagation(); onOpen(f.id) }}>
                          {f.title || 'Formularz bez tytułu'}
                        </button>
                        <p className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                          {fresh.has(f.id) && <Badge className="h-4.5 px-1.5 text-[0.7rem]" data-testid="fresh-badge">nowe</Badge>}
                          <span className="truncate" title={f.filename}>{f.filename}</span>
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden text-sm text-muted-foreground tabular-nums md:table-cell">{date.format(new Date(f.created_at))}</TableCell>
                  <TableCell>
                    {f.open_review > 0
                      ? <span className="inline-flex items-center gap-1.5 rounded-full bg-review-soft px-2.5 py-0.5 text-sm font-medium text-review tabular-nums">
                          <CircleAlert className="size-3.5" aria-hidden /><span aria-hidden>{f.open_review}</span><span className="sr-only">{plural(f.open_review, 'nierozstrzygnięta uwaga', 'nierozstrzygnięte uwagi', 'nierozstrzygniętych uwag')}</span>
                          {f.needs_review > f.open_review && <span className="font-normal opacity-75">/ {f.needs_review}</span>}
                        </span>
                      : <span className="text-sm text-ok">{f.needs_review ? 'Wszystkie rozstrzygnięte' : 'Brak uwag'}</span>}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    {f.proposals > 0
                      ? <span className="inline-flex items-center gap-1.5 text-sm"><BookMarked className="size-3.5 text-primary" aria-hidden />{plural(f.proposals, 'propozycja', 'propozycje', 'propozycji')}</span>
                      : <span className="text-sm text-muted-foreground">—</span>}
                  </TableCell>
                  <TableCell className="pr-3 text-right">
                    <Button variant="ghost" size="icon-sm" aria-label={`Usuń projekt ${f.title || f.filename}`}
                      onClick={(e) => { e.stopPropagation(); setDoomed(f) }}>
                      <Trash2 />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {!items && !error && <p className="text-sm text-muted-foreground" aria-live="polite">Wczytuję projekty…</p>}

      <AlertDialog open={!!doomed} onOpenChange={(v) => !v && !busy && setDoomed(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Usunąć projekt?</AlertDialogTitle>
            <AlertDialogDescription>
              „{doomed?.title || doomed?.filename}” zniknie razem z poprawkami i rozstrzygniętymi uwagami. Tego nie da się cofnąć.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Anuluj</AlertDialogCancel>
            <AlertDialogAction variant="destructive" className="bg-destructive text-white hover:bg-destructive/90" disabled={busy} onClick={(e) => { e.preventDefault(); remove() }}>
              {busy ? 'Usuwam…' : 'Usuń projekt'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
