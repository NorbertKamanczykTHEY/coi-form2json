import jsonata from 'jsonata'
import { useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, Check, ChevronLeft, ChevronRight, CircleAlert, Eye, GitBranch, Info, PenLine, Plus, Trash2, Upload, X } from 'lucide-react'
import { ConditionMark } from '@/components/ConditionDialog'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { dictionaryItems, type Form } from '@/lib/api'
import {
  addField, addSection, canMove, CHOICE, fieldsOf, INPUT, isRequired, moveField, option, removeField, setRequired, tabsOf, text, TYPE_LABEL, usedBy, walk,
  type Field as F, type Q, type Tab,
} from '@/lib/form'
import { plural } from '@/lib/plural'
import { cn } from '@/lib/utils'

// Citizen's view of a COI form (R-V), rendered from the current JSON. Answers live here only; nothing is sent to the API.
export type Review = Map<string, string> // field id -> reason, shown as a red mark
type Answer = string | string[]
// Given by the editor: the mockup gets a "Podgląd / Edycja" switch, and edits go to the same draft as "Pola i uwagi".
export type Editing = {
  change: (fn: (form: Form) => void, o?: { fieldId?: string; undo?: string }) => void
  condition: (fieldId: string, index: number | null) => void
}

// Visible after SHOW; a SECTION/REPEATING_SECTION with nothing visible inside is hidden too (with its title).
function shown(f: F, suffix: string, hidden: Set<string>): boolean {
  if (hidden.has(f.id + suffix)) return false
  if (f.type === 'SECTION') return (f.repeatingSectionGrid ?? []).some((q) => shown(q.field, suffix, hidden))
  if (f.type === 'REPEATING_SECTION') return (f.repeatingSectionGrid ?? []).some((q) => shown(q.field, '', hidden)) // judged by its first copy
  return true
}

// Every rendered field instance: copy i of a REPEATING_SECTION gets suffix `#i` (none for the first) and $repeatingSectionIndex = i.
type Inst = { f: F; suffix: string; index: number }
function instances(qs: Q[] = [], copies: Record<string, number>, suffix = '', index = 0, out: Inst[] = []): Inst[] {
  for (const { field: f } of qs) {
    out.push({ f, suffix, index })
    if (f.type === 'REPEATING_SECTION') for (let i = 0; i < (copies[f.id] ?? 1); i++) instances(f.repeatingSectionGrid, copies, i ? `#${i}` : '', i, out)
    else instances(f.repeatingSectionGrid, copies, suffix, index, out)
  }
  return out
}

export default function Preview({ form, review = new Map(), editing }: { form: Form; review?: Review; editing?: Editing }) {
  const tabs = tabsOf(form)
  const [mode, setMode] = useState<'view' | 'edit'>('view')
  const ed = mode === 'edit' ? editing : undefined
  const [locked, setLocked] = useState<Set<string>>(new Set())
  const [tabId, setTabId] = useState('')
  const [answers, setAnswers] = useState<Record<string, Answer>>({})
  const [copies, setCopies] = useState<Record<string, number>>({})
  const [hidden, setHidden] = useState<Set<string>>(new Set())

  // SHOW: evaluate each query against the form with __userAnswer set on every field, as COI does.
  // A REPEATING_SECTION answers with one [{fieldTechName, answers}] list per copy.
  useEffect(() => {
    if (ed) return
    let live = true
    const data = structuredClone(form) as { tabs?: Tab[] }
    const answer = (f: F, suffix: string) => answers[f.id + suffix] ?? f.defaultValue
    for (const f of (data.tabs ?? []).flatMap((t) => walk(t.questions)) as (F & { __userAnswer?: unknown })[]) {
      f.__userAnswer = f.type !== 'REPEATING_SECTION' ? answer(f, '')
        : Array.from({ length: copies[f.id] ?? 1 }, (_, i) => walk(f.repeatingSectionGrid).map((c) => ({ fieldTechName: c.techName, answers: answer(c, i ? `#${i}` : '') })))
    }
    const all = tabsOf(form).flatMap((t) => instances(t.questions, copies))
    // several states of one type: any that holds counts; a broken query never hides or locks a field
    const ids = (type: string, broken: boolean) => Promise.all(all.filter(({ f }) => f.states?.some((s) => s.type === type)).map(async ({ f, suffix, index }) => {
      const qs = f.states!.filter((s) => s.type === type)
      const ok = await Promise.all(qs.map(async (s) => { try { return !!(await jsonata(s.query).evaluate(data, { repeatingSectionIndex: index })) } catch { return broken } }))
      return ok.some(Boolean) === (type === 'SHOW') ? null : f.id + suffix
    })).then((r) => new Set(r.filter((i): i is string => !!i)))
    Promise.all([ids('SHOW', true), ids('READ_ONLY', false)]).then(([h, l]) => { if (live) { setHidden(h); setLocked(l) } })
    return () => { live = false }
  }, [form, answers, copies, ed])

  // Pages with nothing visible drop out of the steps; if the current one drops out, stay on the nearest earlier page.
  const visible = ed ? tabs : tabs.filter((t) => t.questions.some((q) => shown(q.field, '', hidden)))
  const at = tabs.findIndex((t) => t.id === tabId)
  const found = visible.findIndex((t) => t.id === tabId)
  const step = Math.max(0, found >= 0 ? found : visible.filter((t) => tabs.indexOf(t) < at).length - 1)
  const setStep = (i: number) => setTabId(visible[i].id)
  const tab = visible[step]
  const ctx: Ctx = {
    answers, set: (id, v) => setAnswers((a) => ({ ...a, [id]: v })), hidden: ed ? new Set() : hidden, locked: ed ? new Set() : locked, review, copies,
    setCopies: (id, n) => setCopies((c) => ({ ...c, [id]: n })), form, ed, onCondition: editing?.condition, finish: tab?.type === 'FINISH',
  }
  const title = (form as { title?: string }).title

  return (
    <div className="bg-tray px-3 py-6 sm:px-6 sm:py-10" data-testid="preview" data-mode={mode}>
      {editing && (
        <div className="mx-auto mb-4 flex max-w-3xl flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">{ed ? 'Edytujesz na makiecie: zmiany trafiają do tego samego JSON-a co „Pola i uwagi”.' : 'Makieta działa jak dla obywatela.'}</p>
          <div role="group" aria-label="Tryb makiety" className="inline-flex rounded-lg border bg-card p-0.5 shadow-xs">
            {([['view', 'Podgląd', Eye], ['edit', 'Edycja', PenLine]] as const).map(([m, label, Icon]) => (
              <Button key={m} size="sm" variant={mode === m ? 'default' : 'ghost'} aria-pressed={mode === m} onClick={() => setMode(m)} data-testid={`mode-${m}`}><Icon />{label}</Button>
            ))}
          </div>
        </div>
      )}
      <article className="mx-auto max-w-3xl overflow-hidden rounded-xl bg-card shadow-[0_1px_2px_rgb(27_39_51/0.06),0_8px_24px_-12px_rgb(27_39_51/0.18)]">
        <header className="border-b px-5 pt-5 pb-4 sm:px-8 sm:pt-7">
          <p className="text-sm text-muted-foreground">Wniosek elektroniczny</p>
          <h2 className="mt-1 text-xl leading-snug font-semibold text-balance sm:text-2xl">{title || 'Formularz bez tytułu'}</h2>
          {visible.length > 0 && (
            <ol className="mt-5 flex gap-1 overflow-x-auto pb-1" aria-label="Kroki wniosku">
              {visible.map((t, i) => (
                <li key={t.id} className="min-w-28 flex-1">
                  <button type="button" onClick={() => setStep(i)} aria-current={i === step ? 'step' : undefined}
                    className="group w-full text-left">
                    <span className={cn('block h-1 rounded-full transition-colors', i < step ? 'bg-primary/60' : i === step ? 'bg-primary' : 'bg-border')} />
                    <span className={cn('mt-2 flex items-center gap-1.5 text-xs', i === step ? 'font-medium text-foreground' : 'text-muted-foreground group-hover:text-foreground')}>
                      <span className={cn('grid size-5 shrink-0 place-items-center rounded-full text-[0.7rem] tabular-nums',
                        i < step ? 'bg-primary/15 text-primary' : i === step ? 'bg-primary text-primary-foreground' : 'bg-muted')}>
                        {i < step ? <Check className="size-3" /> : i + 1}
                      </span>
                      <span className="line-clamp-2">{t.title}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          )}
        </header>
        {tab ? (
          <div className="px-5 py-6 sm:px-8">
            <h3 className="mb-5 text-lg font-semibold">{tab.title}</h3>
            <Grid qs={tab.questions} ctx={ctx} suffix="" />
            {ed && (
              <Button variant="outline" className="mt-5 w-full border-dashed" data-testid="add-section"
                onClick={() => ed.change((c) => { addSection(c, tab.id) })}><Plus />Dodaj sekcję</Button>
            )}
            <div className="mt-8 flex justify-between border-t pt-5">
              <Button variant="outline" disabled={step === 0} onClick={() => setStep(step - 1)}><ChevronLeft />Wstecz</Button>
              {step < visible.length - 1
                ? <Button onClick={() => setStep(step + 1)}>Dalej<ChevronRight /></Button>
                : <Button disabled title="Makieta: wniosku nie można wysłać">Wyślij wniosek</Button>}
            </div>
          </div>
        ) : <p className="px-8 py-10 text-sm text-muted-foreground">Formularz nie ma widocznych stron.</p>}
      </article>
    </div>
  )
}

type Ctx = {
  answers: Record<string, Answer>; set: (id: string, v: Answer) => void; hidden: Set<string>; locked: Set<string>; review: Review
  copies: Record<string, number>; setCopies: (id: string, n: number) => void
  form: Form; ed?: Editing; onCondition?: Editing['condition']; finish: boolean
}

// Layout by x/cols on a grid as wide as the widest row (3 in the reference forms); one column on narrow screens.
function Grid({ qs, ctx, suffix }: { qs: Q[]; ctx: Ctx; suffix: string }) {
  const width = Math.max(1, ...qs.map((q) => q.x + q.cols))
  return (
    <div className="grid grid-cols-1 gap-x-4 gap-y-5 sm:[grid-template-columns:repeat(var(--cols),minmax(0,1fr))]" style={{ '--cols': width } as React.CSSProperties}>
      {/* rows flow in y, x order instead of fixed y, so hidden fields leave no gaps */}
      {qs.filter((q) => ctx.ed || shown(q.field, suffix, ctx.hidden)).sort((a, b) => a.y - b.y || a.x - b.x).map((q) => (
        <div key={q.field.id} className="min-w-0 sm:[grid-column:var(--col)]" style={{ '--col': `${q.x + 1} / span ${q.cols}` } as React.CSSProperties}>
          <Field f={q.field} ctx={ctx} suffix={suffix} />
        </div>
      ))}
    </div>
  )
}

function Label({ f, ctx, htmlFor, as = 'label' }: { f: F; ctx: Ctx; htmlFor?: string; as?: 'label' | 'span' }) {
  const why = ctx.review.get(f.id)
  const Tag = as
  return (
    <Tag htmlFor={as === 'label' ? htmlFor : undefined} className="mb-1.5 flex items-start gap-1 text-sm font-medium">
      <span>{f.title}{isRequired(f) && <span className="text-destructive" aria-label="pole wymagane"> *</span>}</span>
      {why && (
        <Tooltip><TooltipTrigger asChild><CircleAlert className="mt-0.5 size-4 shrink-0 text-review" aria-label={`Uwaga do decyzji: ${why}`} /></TooltipTrigger>
          <TooltipContent className="max-w-xs">{why}</TooltipContent></Tooltip>
      )}
      {f.tooltipMessage && (
        <Tooltip><TooltipTrigger asChild><Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-label={f.tooltipMessage} /></TooltipTrigger>
          <TooltipContent className="max-w-xs">{f.tooltipMessage}</TooltipContent></Tooltip>
      )}
    </Tag>
  )
}

const ring = (ctx: Ctx, f: F) => (ctx.review.has(f.id) ? 'rounded-md outline-2 outline-offset-4 outline-review/60 outline-dashed' : '')

function Field({ f, ctx, suffix }: { f: F; ctx: Ctx; suffix: string }) {
  if (ctx.ed && f.type !== 'SECTION' && f.type !== 'REPEATING_SECTION') return <EditField f={f} ctx={ctx} ed={ctx.ed} />
  const key = f.id + suffix // answers of repeated copies are kept apart
  const value = ctx.answers[key] ?? f.defaultValue ?? ''
  const one = Array.isArray(value) ? value[0] ?? '' : value // defaultValue may be a list, e.g. ["Polska"]
  const hint = text(f.description)
  const readOnly = f.readOnly || ctx.locked.has(key)
  const common = { id: key, disabled: readOnly }
  const help = hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
  const mark = ctx.onCondition && <ConditionMark form={ctx.form} f={f} onEdit={(i) => ctx.onCondition!(f.id, i)} />
  const wrap = (body: React.ReactNode) => <div className={ring(ctx, f)} data-field={f.id}>{mark}{body}</div>
  switch (f.type) {
    case 'SECTION':
      return (
        <fieldset className={cn('rounded-lg border bg-muted/30 p-4', ring(ctx, f), ctx.ed && 'border-dashed border-primary/40')} data-section={f.id}>
          {ctx.ed ? <legend className="w-full px-1"><SectionHead f={f} ctx={ctx} ed={ctx.ed} /></legend> : <legend className="px-1 font-semibold">{f.title}</legend>}
          {mark}
          {hint && !ctx.ed && <p className="mb-3 text-sm text-muted-foreground">{hint}</p>}
          <Grid qs={f.repeatingSectionGrid ?? []} ctx={ctx} suffix={suffix} />
          {ctx.ed && <AddField section={f} ctx={ctx} ed={ctx.ed} />}
        </fieldset>
      )
    case 'REPEATING_SECTION':
      return <Repeating f={f} ctx={ctx} />
    case 'TEXT_BLOCK':
      return wrap(<p className="rounded-md border-l-2 border-primary/40 bg-accent/40 px-3 py-2 text-sm">{hint || f.title}</p>)
    case 'CONSENT_SECTION':
      return wrap(
        <div className="space-y-2">
          <Label f={f} ctx={ctx} as="span" />
          {(f.consentSectionConfig?.consents ?? []).map((c, i) => (
            <label key={i} className="flex items-start gap-2.5 text-sm"><Checkbox className="mt-0.5" />{text(c.description)}</label>
          ))}
        </div>,
      )
    case 'TEXTAREA':
      return wrap(<><Label f={f} ctx={ctx} htmlFor={key} /><Textarea {...common} rows={3} value={one} onChange={(e) => ctx.set(key, e.target.value)} />{help}</>)
    case 'DATEPICKER':
      return wrap(<><Label f={f} ctx={ctx} htmlFor={key} /><Input {...common} type="date" value={one} onChange={(e) => ctx.set(key, e.target.value)} />{help}</>)
    case 'NUMBER':
      return wrap(<><Label f={f} ctx={ctx} htmlFor={key} /><Input {...common} type="number" inputMode="decimal" value={one} onChange={(e) => ctx.set(key, e.target.value)} />{help}</>)
    case 'FILE_UPLOADER':
      return wrap(
        <><Label f={f} ctx={ctx} htmlFor={key} />
          <label htmlFor={key} className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-input px-3 py-3 text-sm text-muted-foreground hover:bg-muted/50">
            <Upload className="size-4" />Dodaj plik<input {...common} type="file" className="sr-only" />
          </label>{help}</>,
      )
    case 'SELECT':
      return wrap(<><Label f={f} ctx={ctx} htmlFor={key} /><Select f={f} id={key} disabled={readOnly} value={one} onChange={(v) => ctx.set(key, v)} />{help}</>)
    case 'RADIO':
    case 'CHECKBOX': {
      const multi = f.type === 'CHECKBOX'
      const chosen = ([] as string[]).concat(value || [])
      return wrap(
        <fieldset>
          <legend className="contents"><Label f={f} ctx={ctx} as="span" /></legend>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {(f.options ?? []).map((o) => (
              <label key={o.id} className="inline-flex items-center gap-2 text-sm">
                <input type={multi ? 'checkbox' : 'radio'} name={key} disabled={readOnly} checked={chosen.includes(o.name)} className="size-4 accent-primary"
                  onChange={(e) => ctx.set(key, multi ? (e.target.checked ? [...chosen, o.name] : chosen.filter((c) => c !== o.name)) : o.name)} />
                {o.name}
              </label>
            ))}
          </div>{help}
        </fieldset>,
      )
    }
    default: // TEXT_FIELD and anything unknown
      return wrap(<><Label f={f} ctx={ctx} htmlFor={key} /><Input {...common} value={one} onChange={(e) => ctx.set(key, e.target.value)} />{help}</>)
  }
}

const selectCls = 'h-9 w-full rounded-md border border-input bg-card px-2.5 text-sm disabled:opacity-60'
function Select({ f, id, value, onChange, disabled }: { f: F; id: string; value: string; onChange: (v: string) => void; disabled?: boolean }) {
  const [items, setItems] = useState<string[] | null | undefined>(f.dictionaryName ? undefined : (f.options ?? []).map((o) => o.name))
  useEffect(() => { if (f.dictionaryName) dictionaryItems(f.dictionaryName).then(setItems) }, [f.dictionaryName])
  const placeholder = items === undefined ? 'Wczytuję słownik…' : items === null ? `Słownik ${f.dictionaryName} jest niedostępny` : 'Wybierz'
  return (
    <select id={id} disabled={disabled} value={value} onChange={(e) => onChange(e.target.value)} className={selectCls}>
      <option value="">{placeholder}</option>
      {(items ?? []).map((n, i) => <option key={i} value={n}>{n}</option>)}
    </select>
  )
}

function Repeating({ f, ctx }: { f: F; ctx: Ctx }) {
  const copies = ctx.copies[f.id] ?? 1
  return (
    <fieldset className={cn('space-y-4 rounded-lg border bg-muted/30 p-4', ring(ctx, f), ctx.ed && 'border-dashed border-primary/40')} data-section={f.id}>
      {ctx.ed ? <legend className="w-full px-1"><SectionHead f={f} ctx={ctx} ed={ctx.ed} /></legend> : <legend className="px-1 font-semibold">{f.title}</legend>}
      {ctx.onCondition && <ConditionMark form={ctx.form} f={f} onEdit={(i) => ctx.onCondition!(f.id, i)} />}
      {Array.from({ length: copies }, (_, i) => (
        <div key={i} className={i ? 'border-t border-dashed pt-4' : ''}>
          {copies > 1 && <p className="mb-2 text-xs font-medium text-muted-foreground">Pozycja {i + 1}</p>}
          <Grid qs={f.repeatingSectionGrid ?? []} ctx={ctx} suffix={i ? `#${i}` : ''} />
        </div>
      ))}
      {ctx.ed ? <AddField section={f} ctx={ctx} ed={ctx.ed} /> : <div className="flex gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => ctx.setCopies(f.id, copies + 1)}><Plus />Dodaj kolejną</Button>
        {copies > 1 && <Button type="button" variant="ghost" size="sm" onClick={() => ctx.setCopies(f.id, copies - 1)}>Usuń ostatnią</Button>}
      </div>}
    </fieldset>
  )
}

// ---- edit mode ---------------------------------------------------------------
const setField = (ed: Editing, id: string, fn: (f: F) => void) =>
  ed.change((c) => { const f = fieldsOf(c).find((x) => x.id === id); if (f) fn(f) }, { fieldId: id })

// Move, condition and delete buttons of one field or section.
function Tools({ f, ctx, ed }: { f: F; ctx: Ctx; ed: Editing }) {
  const name = f.title || TYPE_LABEL[f.type] || f.type
  const refs = usedBy(ctx.form, f)
  const del = () => ed.change((c) => removeField(c, f.id), {
    undo: `Usunięto „${name}”${refs ? `. Uwaga: odwołuje się do niego ${plural(refs, 'warunek', 'warunki', 'warunków')}, zapis je odrzuci` : ''}`,
  })
  return (
    <div className="flex shrink-0 items-center gap-0.5">
      <Button variant="ghost" size="icon-sm" aria-label={`Przesuń wyżej: ${name}`} disabled={!canMove(ctx.form, f.id, -1)} onClick={() => ed.change((c) => moveField(c, f.id, -1))}><ArrowUp /></Button>
      <Button variant="ghost" size="icon-sm" aria-label={`Przesuń niżej: ${name}`} disabled={!canMove(ctx.form, f.id, 1)} onClick={() => ed.change((c) => moveField(c, f.id, 1))}><ArrowDown /></Button>
      {!f.states?.length && ctx.onCondition && (
        <Button variant="ghost" size="icon-sm" aria-label={`Dodaj warunek: ${name}`} title="Dodaj warunek" onClick={() => ctx.onCondition!(f.id, null)}><GitBranch /></Button>
      )}
      <Button variant="ghost" size="icon-sm" className="text-destructive hover:text-destructive" aria-label={`Usuń: ${name}`} onClick={del} data-testid="delete-field"><Trash2 /></Button>
    </div>
  )
}

function SectionHead({ f, ctx, ed }: { f: F; ctx: Ctx; ed: Editing }) {
  return (
    <div className="flex items-center gap-2">
      <span className="shrink-0 text-xs font-medium text-primary">{TYPE_LABEL[f.type]}</span>
      <Input aria-label="Tytuł sekcji" value={f.title ?? ''} className="h-8 bg-card font-semibold" onChange={(e) => setField(ed, f.id, (x) => { x.title = e.target.value })} />
      <Tools f={f} ctx={ctx} ed={ed} />
    </div>
  )
}

const NEW_TYPES = ['TEXT_FIELD', 'TEXTAREA', 'NUMBER', 'DATEPICKER', 'RADIO', 'CHECKBOX', 'SELECT', 'FILE_UPLOADER', 'TEXT_BLOCK']
function AddField({ section, ctx, ed }: { section: F; ctx: Ctx; ed: Editing }) {
  const types = ctx.finish ? ['TEXT_BLOCK'] : NEW_TYPES // R3: no input fields on the FINISH page
  const [type, setType] = useState(types[0])
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-dashed pt-3">
      <select aria-label={`Typ nowego pola w sekcji ${section.title}`} value={type} onChange={(e) => setType(e.target.value)} className={cn(selectCls, 'h-8 w-auto')}>
        {types.map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
      </select>
      <Button variant="outline" size="sm" onClick={() => ed.change((c) => { addField(c, section.id, type) })} data-testid="add-field"><Plus />Dodaj pole</Button>
    </div>
  )
}

function EditField({ f, ctx, ed }: { f: F; ctx: Ctx; ed: Editing }) {
  const choice = CHOICE.includes(f.type) && !f.dictionaryName
  const input = INPUT.includes(f.type)
  const id = `ed-${f.id}`
  return (
    <div data-field={f.id} data-testid="edit-field"
      className={cn('rounded-lg border border-dashed border-primary/30 bg-card p-3 transition-colors hover:border-primary/60 focus-within:border-solid focus-within:border-primary', ring(ctx, f))}>
      {ctx.onCondition && <ConditionMark form={ctx.form} f={f} onEdit={(i) => ctx.onCondition!(f.id, i)} />}
      <div className="flex items-center gap-2">
        {f.type === 'TEXT_BLOCK'
          ? <span className="flex-1 text-xs font-medium text-primary">{TYPE_LABEL[f.type]}</span>
          : <Input id={id} aria-label="Etykieta pola" value={f.title ?? ''} placeholder="Etykieta" className="h-8 font-medium" data-testid="label-input"
              onChange={(e) => setField(ed, f.id, (x) => { x.title = e.target.value })} />}
        <Tools f={f} ctx={ctx} ed={ed} />
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>{TYPE_LABEL[f.type] ?? f.type}{f.dictionaryName ? `, słownik ${f.dictionaryName}` : ''}</span>
        <code>{f.techName}</code>
        {input && (
          <label className="ml-auto inline-flex items-center gap-1.5 text-foreground">
            <Switch checked={isRequired(f)} onCheckedChange={(v) => setField(ed, f.id, (x) => setRequired(x, v))} aria-label={`Pole wymagane: ${f.title}`} />Wymagane
          </label>
        )}
      </div>
      {choice ? <Options f={f} ed={ed} /> : f.type === 'TEXT_BLOCK' ? (
        <Textarea aria-label="Treść informacji" rows={3} className="mt-2" value={text(f.description)} onChange={(e) => setField(ed, f.id, (x) => { x.description = e.target.value })} />
      ) : f.type === 'CONSENT_SECTION' ? (
        <ul className="mt-2 space-y-1 text-sm text-muted-foreground">{(f.consentSectionConfig?.consents ?? []).map((c, i) => <li key={i} className="line-clamp-2">☐ {text(c.description)}</li>)}</ul>
      ) : (
        <div aria-hidden className="mt-2 flex h-9 items-center rounded-md border bg-muted/40 px-3 text-sm text-muted-foreground">{f.type === 'FILE_UPLOADER' ? <><Upload className="mr-2 size-4" />Dodaj plik</> : TYPE_LABEL[f.type] ?? 'Pole'}</div>
      )}
      {f.type !== 'TEXT_BLOCK' && f.type !== 'CONSENT_SECTION' && (
        <Textarea aria-label="Podpowiedź pod polem" rows={1} placeholder="Podpowiedź pod polem (opcjonalnie)" className="mt-2 min-h-8 text-xs"
          value={text(f.description)} onChange={(e) => setField(ed, f.id, (x) => { x.description = e.target.value })} />
      )}
    </div>
  )
}

function Options({ f, ed }: { f: F; ed: Editing }) {
  const opts = f.options ?? []
  const set = (fn: (o: NonNullable<F['options']>) => void) => setField(ed, f.id, (x) => { x.options = [...(x.options ?? [])]; fn(x.options) })
  return (
    <fieldset className="mt-2 space-y-1.5">
      <legend className="sr-only">Opcje pola {f.title}</legend>
      {opts.map((o, i) => (
        <div key={o.id} className="flex items-center gap-2">
          <span aria-hidden className={cn('size-3.5 shrink-0 border border-input', f.type === 'CHECKBOX' ? 'rounded-sm' : 'rounded-full')} />
          <Input aria-label={`Opcja ${i + 1}`} value={o.name} className="h-8" data-testid="option-input"
            onChange={(e) => set((l) => { l[i] = { ...l[i], name: e.target.value } })} />
          <Button variant="ghost" size="icon-sm" aria-label={`Usuń opcję ${o.name}`} disabled={opts.length < 2} onClick={() => set((l) => { l.splice(i, 1) })}><X /></Button>
        </div>
      ))}
      <Button variant="ghost" size="xs" onClick={() => set((l) => { l.push(option(`Opcja ${l.length + 1}`)) })}><Plus />Dodaj opcję</Button>
    </fieldset>
  )
}
