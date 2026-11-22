import { conditionMsg } from '@/lib/messages'
import { useMemo, useState } from 'react'
import { CircleAlert, CircleCheck, GitBranch, Plus, Trash2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import type { Form } from '@/lib/api'
import { check, controllers, describe, emit, parse, refKey, type Model, type Row } from '@/lib/condition'
import { locate, type Field } from '@/lib/form'
import { cn } from '@/lib/utils'

export type State = { type: string; query: string }
const STATE_LABEL: Record<string, string> = { SHOW: 'Widoczne, gdy', READ_ONLY: 'Tylko do odczytu, gdy' }
const selectCls = 'h-9 w-full rounded-md border border-input bg-card px-2.5 text-sm'
const blank = (): Model => ({ negate: false, join: 'and', rows: [] })

// Edits one `states` entry of a field: JSONata text with live checks, and a builder that rewrites the text on every change.
export default function ConditionDialog({ form, owner, state, onSave, onRemove, onClose }: {
  form: Form; owner: Field; state: State | null; onSave: (s: State) => void; onRemove?: () => void; onClose: () => void
}) {
  const [type, setType] = useState(state?.type ?? 'SHOW')
  const [text, setText] = useState(state?.query ?? '')
  const [model, setModel] = useState<Model | null>(() => (state?.query ? parse(state.query) : blank()))
  const [tab, setTab] = useState(state?.query && !model ? 'text' : 'graphic')
  const problems = useMemo(() => check(text, form, owner), [text, form, owner])

  // choice fields that may drive this one: not itself, and inside a repeating section only from the same section
  const section = locate(form, owner.id)?.parent?.field.id
  const options = controllers(form).filter((c) => c.tech !== owner.techName && (!c.repeating || c.owner === section))
  const byKey = new Map(options.map((c) => [c.key, c]))

  const fromText = (t: string) => { setText(t); setModel(t.trim() ? parse(t) : blank()) }
  const fromModel = (m: Model) => { setModel(m); setText(emit(m)) }
  const setRow = (i: number, r: Partial<Row>) => model && fromModel({ ...model, rows: model.rows.map((x, j) => (j === i ? { ...x, ...r } : x)) })
  const addRow = () => {
    const c = options[0]
    if (model && c) fromModel({ ...model, rows: [...model.rows, { page: c.page, section: c.section, tech: c.tech, repeating: c.repeating, op: 'in', values: [] }] })
  }
  const ok = problems.length === 0
  const errId = 'cond-errors'

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="flex max-h-[90vh] flex-col gap-4 sm:max-w-3xl" data-testid="condition-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><GitBranch className="size-5 text-primary" aria-hidden />Warunek: {owner.title || owner.techName}</DialogTitle>
          <DialogDescription>Wyrażenie JSONata w kształcie generatora. Konstruktor od razu przepisuje tekst; tekst sprawdzamy na bieżąco.</DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Label htmlFor="cond-type">Rodzaj</Label>
          <select id="cond-type" className={cn(selectCls, 'w-auto')} value={type} onChange={(e) => setType(e.target.value)}>
            <option value="SHOW">Pokaż, gdy warunek jest spełniony (SHOW)</option>
            <option value="READ_ONLY">Tylko do odczytu, gdy warunek jest spełniony (READ_ONLY)</option>
          </select>
        </div>

        <Tabs value={tab} onValueChange={setTab} className="min-h-0 flex-1 gap-3 overflow-y-auto">
          <TabsList>
            <TabsTrigger value="graphic">Graficzny</TabsTrigger>
            <TabsTrigger value="text">Tekst</TabsTrigger>
          </TabsList>

          <TabsContent value="graphic" className="space-y-3">
            {!model ? (
              <div className="rounded-lg border border-dashed p-4 text-sm" role="status" data-testid="not-graphical">
                <p className="font-medium">Tego wyrażenia nie da się pokazać w konstruktorze.</p>
                <p className="mt-1 text-muted-foreground">Konstruktor obsługuje warunki „pole jest / nie jest jedną z opcji”, połączone jednym spójnikiem I albo LUB, z opcjonalną negacją całości. Edytuj je w zakładce Tekst albo zacznij od nowa.</p>
                <Button variant="outline" size="sm" className="mt-3" onClick={() => fromModel(blank())}>Zacznij od nowa w konstruktorze</Button>
              </div>
            ) : (
              <>
                {model.rows.length > 1 && (
                  <div className="flex items-center gap-2 text-sm" role="radiogroup" aria-label="Łączenie warunków">
                    <span className="text-muted-foreground">Spełnione mają być</span>
                    {(['and', 'or'] as const).map((j) => (
                      <Button key={j} size="xs" variant={model.join === j ? 'default' : 'outline'} role="radio" aria-checked={model.join === j}
                        onClick={() => fromModel({ ...model, join: j })}>{j === 'and' ? 'wszystkie (I)' : 'dowolny (LUB)'}</Button>
                    ))}
                  </div>
                )}
                <ol className="space-y-2">
                  {model.rows.map((r, i) => {
                    const c = byKey.get(refKey(r))
                    return (
                      <li key={i} className="rounded-lg border bg-muted/30 p-3" data-testid="cond-row">
                        {i > 0 && <p className="-mt-1 mb-2 text-xs font-semibold tracking-wide text-primary uppercase">{model.join === 'and' ? 'i' : 'lub'}</p>}
                        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_12rem_auto]">
                          <div>
                            <Label htmlFor={`cond-f-${i}`} className="sr-only">Pole sterujące</Label>
                            <select id={`cond-f-${i}`} className={selectCls} value={c ? c.key : ''} aria-label="Pole sterujące"
                              onChange={(e) => { const n = byKey.get(e.target.value)!; setRow(i, { page: n.page, section: n.section, tech: n.tech, repeating: n.repeating, values: [] }) }}>
                              {!c && <option value="">{r.tech} (nie ma w formularzu)</option>}
                              {options.map((o) => <option key={o.key} value={o.key}>{o.label} · {o.page}</option>)}
                            </select>
                          </div>
                          <select className={selectCls} value={r.op} aria-label="Operator" onChange={(e) => setRow(i, { op: e.target.value as Row['op'] })}>
                            <option value="in">jest jedną z</option>
                            <option value="notin">nie jest żadną z</option>
                          </select>
                          <Button variant="ghost" size="icon-sm" aria-label={`Usuń warunek ${i + 1}`} onClick={() => fromModel({ ...model, rows: model.rows.filter((_, j) => j !== i) })}><X /></Button>
                        </div>
                        <fieldset className="mt-2">
                          <legend className="sr-only">Opcje</legend>
                          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
                            {(c?.options ?? r.values).map((o) => (
                              <label key={o} className="inline-flex items-center gap-2 text-sm">
                                <Checkbox checked={r.values.includes(o)} onCheckedChange={(v) => setRow(i, { values: v ? [...r.values, o] : r.values.filter((x) => x !== o) })} />{o}
                              </label>
                            ))}
                          </div>
                          {!r.values.length && <p className="mt-1 text-xs text-review">Zaznacz co najmniej jedną opcję, inaczej ten wiersz nie trafi do wyrażenia.</p>}
                        </fieldset>
                      </li>
                    )
                  })}
                </ol>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <Button variant="outline" size="sm" onClick={addRow} disabled={!options.length}><Plus />Dodaj warunek</Button>
                  <label className="flex items-center gap-2 text-sm">
                    <Switch checked={model.negate} onCheckedChange={(v) => fromModel({ ...model, negate: v })} aria-label="Negacja całości" />Odwróć całość (NIE)
                  </label>
                </div>
                {!options.length && <p className="text-sm text-muted-foreground">W formularzu nie ma pól wyboru z opcjami, od których to pole mogłoby zależeć.</p>}
              </>
            )}
          </TabsContent>

          <TabsContent value="text" className="space-y-2">
            <Label htmlFor="cond-text">Wyrażenie JSONata</Label>
            <Textarea id="cond-text" rows={8} spellCheck={false} value={text} onChange={(e) => fromText(e.target.value)}
              aria-invalid={!ok} aria-describedby={errId} className="font-mono text-xs leading-relaxed" data-testid="cond-text" />
          </TabsContent>
        </Tabs>

        <div id={errId} aria-live="polite" className="text-sm">
          {ok
            ? <p className="flex items-start gap-2 text-ok"><CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden /><span><span className="font-medium">Poprawne.</span> {STATE_LABEL[type]}: {describe(text, form)}</span></p>
            : <ul className="space-y-1 text-destructive" data-testid="cond-errors">
                {problems.map((p, i) => { const m = conditionMsg(p.message); return <li key={i} className="flex items-start gap-2"><CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                  <span><span className="font-medium">{m.title}{p.position != null && <span className="font-normal text-muted-foreground"> (znak {p.position})</span>}:</span> {m.why} <span className="text-foreground">{m.action}</span>
                    {m.original !== m.why && <span className="block text-xs text-muted-foreground">{p.message}</span>}</span></li> })}
              </ul>}
        </div>

        <DialogFooter className="sm:justify-between">
          {onRemove ? <Button variant="ghost" className="text-destructive" onClick={onRemove}><Trash2 />Usuń warunek</Button> : <span />}
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>Anuluj</Button>
            <Button disabled={!ok} onClick={() => onSave({ type, query: text.trim() })} data-testid="cond-save">Zapisz</Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// The mark on a conditional field: icon, the condition in words, and the edit button.
export function ConditionMark({ form, f, onEdit }: { form: Form; f: Field; onEdit?: (index: number) => void }) {
  const states = (f.states ?? []).filter((s) => s.query)
  if (!states.length) return null
  return (
    <div className="mb-2 flex flex-col gap-1" data-testid="condition-mark">
      {states.map((s, i) => (
        <div key={i} className="flex items-center gap-2 rounded-md bg-accent/60 px-2 py-1 text-xs text-accent-foreground">
          <GitBranch className="size-3.5 shrink-0 text-primary" aria-hidden />
          <span className="min-w-0 flex-1 truncate" title={s.query}><span className="font-medium">{STATE_LABEL[s.type] ?? s.type}:</span> {describe(s.query, form)}</span>
          {onEdit && <Button size="xs" variant="ghost" className="h-6 shrink-0" onClick={() => onEdit(i)} data-testid="edit-condition">Edytuj warunek</Button>}
        </div>
      ))}
    </div>
  )
}
