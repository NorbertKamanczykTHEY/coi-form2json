import { useRef, useState } from 'react'
import { AlertTriangle, ArrowUpRight, CheckCircle2, ChevronRight, CircleDashed, FileUp, Loader2, Repeat2, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import type { Info } from '@/lib/api'
import { clearFinished, enqueue, useQueue, type Job, type LogEntry } from '@/lib/queue'
import { IMPORT_CONCURRENCY } from '@/config'
import { cn } from '@/lib/utils'

const STAGE: Record<string, string> = { parse: 'Odczyt dokumentu', extract: 'Rozpoznanie pól', generate: 'Budowa formularza' }
const num = (v: number, d: number) => v.toLocaleString('pl-PL', { maximumFractionDigits: d, minimumFractionDigits: d })
const money = (v?: number) => (v == null ? '' : `${num(v, v < 0.1 ? 4 : 2)} USD`)
const secs = (v?: number) => (v == null ? '' : `${num(v, v < 10 ? 1 : 0)} s`)

export default function ImportDialog({ open, onOpenChange, info, onOpenForm }: {
  open: boolean; onOpenChange: (v: boolean) => void; info: Info | null; onOpenForm: (id: string) => void
}) {
  const jobs = useQueue()
  const input = useRef<HTMLInputElement>(null)
  const [drag, setDrag] = useState(false)
  const done = jobs.filter((j) => j.status === 'done').length
  const busy = jobs.filter((j) => j.status === 'running' || j.status === 'waiting').length
  const add = (files: FileList | null) => files?.length && enqueue([...files], info)
  const l = info?.limits

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[88vh] flex-col gap-4 sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import plików</DialogTitle>
          <DialogDescription>
            Każdy plik staje się osobnym projektem. Możesz dokładać kolejne pliki w trakcie i zamknąć to okno: import trwa dalej.
          </DialogDescription>
        </DialogHeader>

        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files) }}
          className={cn('flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors',
            drag ? 'border-primary bg-accent' : 'border-input bg-muted/50')}
        >
          <FileUp className="size-6 text-primary" aria-hidden />
          <p className="text-sm">Przeciągnij pliki tutaj albo</p>
          <Button type="button" onClick={() => input.current?.click()}>Wybierz pliki</Button>
          <input ref={input} type="file" multiple className="sr-only" aria-label="Pliki formularzy" data-testid="import-input"
            onChange={(e) => { add(e.target.files); e.target.value = '' }} />
          {l && (
            <p className="max-w-md text-xs text-muted-foreground">
              {l.extensions.map((e) => e.toUpperCase()).join(', ')}, do {l.max_file_mb} MB, nazwa do {l.max_filename_len} znaków.
              Naraz przetwarzane są {IMPORT_CONCURRENCY} pliki.
            </p>
          )}
        </div>

        {jobs.length > 0 && (
          <div className="flex min-h-0 flex-1 flex-col gap-2">
            <div className="flex items-center justify-between text-sm">
              <p aria-live="polite"><span className="font-medium tabular-nums">{done} z {jobs.length}</span> gotowe{busy ? `, ${busy} w toku` : ''}</p>
              {jobs.length > busy && <Button variant="ghost" size="sm" onClick={clearFinished}>Wyczyść zakończone</Button>}
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto rounded-lg border">
              <ul className="divide-y" aria-label="Kolejka importu">
                {jobs.map((j) => <Row key={j.key} job={j} onOpenForm={onOpenForm} />)}
              </ul>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{busy ? 'Zamknij (import trwa dalej)' : 'Zamknij'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function StatusIcon({ s }: { s: Job['status'] }) {
  if (s === 'done') return <CheckCircle2 className="size-5 text-ok" aria-label="Gotowe" />
  if (s === 'rejected') return <XCircle className="size-5 text-destructive" aria-label="Odrzucony" />
  if (s === 'running') return <Loader2 className="size-5 animate-spin text-primary" aria-label="Przetwarzanie" />
  return <CircleDashed className="size-5 text-muted-foreground" aria-label="W kolejce" />
}

function Row({ job: j, onOpenForm }: { job: Job; onOpenForm: (id: string) => void }) {
  const last = [...j.log].reverse().find((e) => e.kind === 'stage') as Extract<LogEntry, { kind: 'stage' }> | undefined
  const sub = j.status === 'rejected' ? j.reason
    : j.status === 'done' ? `Gotowe w ${secs(((j.ended ?? 0) - (j.started ?? 0)) / 1000)}`
    : j.status === 'running' ? (last ? `${STAGE[last.stage] ?? last.stage}${last.status === 'start' ? '…' : ''}` : 'Wysyłanie…')
    : 'W kolejce'
  return (
    <li data-testid="queue-row" data-status={j.status}>
      <Collapsible>
        <div className="flex items-center gap-3 px-3 py-2.5">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={`Pokaż przebieg: ${j.name}`} className="[&[data-state=open]>svg]:rotate-90">
              <ChevronRight className="transition-transform" />
            </Button>
          </CollapsibleTrigger>
          <StatusIcon s={j.status} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium" title={j.name}>{j.name}</p>
            <p className={cn('text-xs', j.status === 'rejected' ? 'text-destructive' : 'text-muted-foreground')}>{sub}</p>
          </div>
          {j.id && <Button variant="outline" size="sm" onClick={() => onOpenForm(j.id!)}>Otwórz<ArrowUpRight /></Button>}
        </div>
        <CollapsibleContent>
          <ol className="mx-3 mb-3 ml-14 space-y-1.5 border-l-2 border-border pl-4 text-xs" data-testid="queue-log">
            {j.log.length === 0 && <li className="text-muted-foreground">{j.status === 'rejected' ? 'Plik nie został wysłany.' : 'Brak zdarzeń.'}</li>}
            {j.log.map((e, i) => <Entry key={i} e={e} t0={j.started ?? e.at} />)}
          </ol>
        </CollapsibleContent>
      </Collapsible>
    </li>
  )
}

function Entry({ e, t0 }: { e: LogEntry; t0: number }) {
  const at = <span className="w-12 shrink-0 tabular-nums text-muted-foreground">+{secs((e.at - t0) / 1000)}</span>
  const row = (icon: React.ReactNode, body: React.ReactNode, tone = '') => (
    <li className={cn('flex items-start gap-2', tone)}>{at}<span className="mt-px shrink-0">{icon}</span><span className="min-w-0">{body}</span></li>
  )
  switch (e.kind) {
    case 'stage': {
      const extra = [e.parser && `parser ${e.parser}`, secs(e.seconds), e.fields != null && `${e.fields} pól`, money(e.cost)].filter(Boolean).join(', ')
      return row(e.status === 'done' ? <CheckCircle2 className="size-3.5 text-ok" /> : <CircleDashed className="size-3.5 text-muted-foreground" />,
        <><span className="font-medium">{STAGE[e.stage] ?? e.stage}</span> {e.status === 'done' ? 'zakończony' : 'rozpoczęty'}{extra && <span className="text-muted-foreground"> ({extra})</span>}</>)
    }
    case 'escalation':
      return row(<Repeat2 className="size-3.5 text-primary" />,
        <>Eskalacja{e.page != null ? ` (strona ${e.page + 1})` : ''}: <span className="font-medium">{e.model ?? e.step}</span>{' '}
          {e.accepted ? 'wynik przyjęty' : 'wynik odrzucony'}{e.error && <span className="block break-words text-muted-foreground">{e.error}</span>}</>)
    case 'warning':
      return row(<AlertTriangle className="size-3.5 text-amber-600" />, <span className="break-words">{e.message}</span>, 'text-amber-900')
    case 'result':
      return row(<CheckCircle2 className="size-3.5 text-ok" />,
        <><span className="font-medium">Projekt zapisany</span> <span className="text-muted-foreground">({[e.review ? `${e.review} uwag do decyzji` : 'bez uwag', secs(e.seconds), money(e.cost)].filter(Boolean).join(', ')})</span></>)
    case 'error':
      return row(<XCircle className="size-3.5 text-destructive" />, <span className="break-words">{e.message}</span>, 'text-destructive')
  }
}
