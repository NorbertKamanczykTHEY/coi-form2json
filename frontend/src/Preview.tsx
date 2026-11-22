import jsonata from 'jsonata'
import { useEffect, useState } from 'react'
import { Check, ChevronLeft, ChevronRight, CircleAlert, Info, Plus, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { dictionaryItems, type Form } from '@/lib/api'
import { isRequired, tabsOf, text, walk, type Field as F, type Q, type Tab } from '@/lib/form'
import { cn } from '@/lib/utils'

// Citizen's view of a COI form (R-V), rendered from the current JSON. Answers live here only; nothing is sent to the API.
export type Review = Map<string, string> // field id -> reason, shown as a red mark
type Answer = string | string[]

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

export default function Preview({ form, review = new Map() }: { form: Form; review?: Review }) {
  const tabs = tabsOf(form)
  const [tabId, setTabId] = useState('')
  const [answers, setAnswers] = useState<Record<string, Answer>>({})
  const [copies, setCopies] = useState<Record<string, number>>({})
  const [hidden, setHidden] = useState<Set<string>>(new Set())

  // SHOW: evaluate each query against the form with __userAnswer set on every field, as COI does.
  // A REPEATING_SECTION answers with one [{fieldTechName, answers}] list per copy.
  useEffect(() => {
    let live = true
    const data = structuredClone(form) as { tabs?: Tab[] }
    const answer = (f: F, suffix: string) => answers[f.id + suffix] ?? f.defaultValue
    for (const f of (data.tabs ?? []).flatMap((t) => walk(t.questions)) as (F & { __userAnswer?: unknown })[]) {
      f.__userAnswer = f.type !== 'REPEATING_SECTION' ? answer(f, '')
        : Array.from({ length: copies[f.id] ?? 1 }, (_, i) => walk(f.repeatingSectionGrid).map((c) => ({ fieldTechName: c.techName, answers: answer(c, i ? `#${i}` : '') })))
    }
    const all = tabsOf(form).flatMap((t) => instances(t.questions, copies))
    Promise.all(all.filter(({ f }) => f.states?.some((s) => s.type === 'SHOW')).map(async ({ f, suffix, index }) => {
      const shows = f.states!.filter((s) => s.type === 'SHOW')
      // a field with several SHOW states is shown when any of them holds; a broken query never hides a field
      const ok = await Promise.all(shows.map((s) => jsonata(s.query).evaluate(data, { repeatingSectionIndex: index }).then(Boolean).catch(() => true)))
      return ok.some(Boolean) ? null : f.id + suffix
    })).then((ids) => live && setHidden(new Set(ids.filter((i): i is string => !!i))))
    return () => { live = false }
  }, [form, answers, copies])

  // Pages with nothing visible drop out of the steps; if the current one drops out, stay on the nearest earlier page.
  const visible = tabs.filter((t) => t.questions.some((q) => shown(q.field, '', hidden)))
  const at = tabs.findIndex((t) => t.id === tabId)
  const found = visible.findIndex((t) => t.id === tabId)
  const step = Math.max(0, found >= 0 ? found : visible.filter((t) => tabs.indexOf(t) < at).length - 1)
  const setStep = (i: number) => setTabId(visible[i].id)
  const tab = visible[step]
  const ctx: Ctx = { answers, set: (id, v) => setAnswers((a) => ({ ...a, [id]: v })), hidden, review, copies, setCopies: (id, n) => setCopies((c) => ({ ...c, [id]: n })) }
  const title = (form as { title?: string }).title

  return (
    <div className="bg-tray px-3 py-6 sm:px-6 sm:py-10" data-testid="preview">
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
  answers: Record<string, Answer>; set: (id: string, v: Answer) => void; hidden: Set<string>; review: Review
  copies: Record<string, number>; setCopies: (id: string, n: number) => void
}

// Layout by x/cols on a grid as wide as the widest row (3 in the reference forms); one column on narrow screens.
function Grid({ qs, ctx, suffix }: { qs: Q[]; ctx: Ctx; suffix: string }) {
  const width = Math.max(1, ...qs.map((q) => q.x + q.cols))
  return (
    <div className="grid grid-cols-1 gap-x-4 gap-y-5 sm:[grid-template-columns:repeat(var(--cols),minmax(0,1fr))]" style={{ '--cols': width } as React.CSSProperties}>
      {/* rows flow in y, x order instead of fixed y, so hidden fields leave no gaps */}
      {qs.filter((q) => shown(q.field, suffix, ctx.hidden)).sort((a, b) => a.y - b.y || a.x - b.x).map((q) => (
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
  const key = f.id + suffix // answers of repeated copies are kept apart
  const value = ctx.answers[key] ?? f.defaultValue ?? ''
  const one = Array.isArray(value) ? value[0] ?? '' : value // defaultValue may be a list, e.g. ["Polska"]
  const hint = text(f.description)
  const common = { id: key, disabled: f.readOnly }
  const help = hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
  const wrap = (body: React.ReactNode) => <div className={ring(ctx, f)} data-field={f.id}>{body}</div>
  switch (f.type) {
    case 'SECTION':
      return (
        <fieldset className={cn('rounded-lg border bg-muted/30 p-4', ring(ctx, f))}>
          <legend className="px-1 font-semibold">{f.title}</legend>
          {hint && <p className="mb-3 text-sm text-muted-foreground">{hint}</p>}
          <Grid qs={f.repeatingSectionGrid ?? []} ctx={ctx} suffix={suffix} />
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
      return wrap(<><Label f={f} ctx={ctx} htmlFor={key} /><Select f={f} id={key} value={one} onChange={(v) => ctx.set(key, v)} />{help}</>)
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
                <input type={multi ? 'checkbox' : 'radio'} name={key} disabled={f.readOnly} checked={chosen.includes(o.name)} className="size-4 accent-primary"
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
function Select({ f, id, value, onChange }: { f: F; id: string; value: string; onChange: (v: string) => void }) {
  const [items, setItems] = useState<string[] | null | undefined>(f.dictionaryName ? undefined : (f.options ?? []).map((o) => o.name))
  useEffect(() => { if (f.dictionaryName) dictionaryItems(f.dictionaryName).then(setItems) }, [f.dictionaryName])
  const placeholder = items === undefined ? 'Wczytuję słownik…' : items === null ? `Słownik ${f.dictionaryName} jest niedostępny` : 'Wybierz'
  return (
    <select id={id} disabled={f.readOnly} value={value} onChange={(e) => onChange(e.target.value)} className={selectCls}>
      <option value="">{placeholder}</option>
      {(items ?? []).map((n, i) => <option key={i} value={n}>{n}</option>)}
    </select>
  )
}

function Repeating({ f, ctx }: { f: F; ctx: Ctx }) {
  const copies = ctx.copies[f.id] ?? 1
  return (
    <fieldset className={cn('space-y-4 rounded-lg border bg-muted/30 p-4', ring(ctx, f))}>
      <legend className="px-1 font-semibold">{f.title}</legend>
      {Array.from({ length: copies }, (_, i) => (
        <div key={i} className={i ? 'border-t border-dashed pt-4' : ''}>
          {copies > 1 && <p className="mb-2 text-xs font-medium text-muted-foreground">Pozycja {i + 1}</p>}
          <Grid qs={f.repeatingSectionGrid ?? []} ctx={ctx} suffix={i ? `#${i}` : ''} />
        </div>
      ))}
      <div className="flex gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => ctx.setCopies(f.id, copies + 1)}><Plus />Dodaj kolejną</Button>
        {copies > 1 && <Button type="button" variant="ghost" size="sm" onClick={() => ctx.setCopies(f.id, copies - 1)}>Usuń ostatnią</Button>}
      </div>
    </fieldset>
  )
}
