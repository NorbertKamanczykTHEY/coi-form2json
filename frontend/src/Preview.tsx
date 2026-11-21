import jsonata from 'jsonata'
import { useEffect, useState } from 'react'

// Read-only render of a COI form (R-V). Answers live here only; nothing is sent to the API.
type Q = { x: number; y: number; rows: number; cols: number; field: F }
type F = {
  id: string; type: string; techName?: string; title?: string; description?: string; tooltipMessage?: string
  options?: { id: string; name: string }[]; validation?: unknown[]; dictionaryName?: string; readOnly?: boolean
  defaultValue?: Answer; repeatingSectionGrid?: Q[]; states?: { type: string; query: string }[]
  consentSectionConfig?: { consents?: { description?: string }[]; required?: boolean }
}
type Tab = { id: string; title: string; type: string; questions: Q[] }
export type Review = Map<string, string> // field id or techName -> reason
type Answer = string | string[]

// HTML from the form (descriptions, consents) shown as plain text: it comes from an LLM, so no innerHTML.
const text = (html?: string) => (html ? new DOMParser().parseFromString(html, 'text/html').body.textContent?.trim() ?? '' : '')
// validation is a list in the schema, but reference #1 has `{}` in places
const required = (f: F) => Array.isArray(f.validation) && f.validation.some((v) => v === 'REQUIRED' || (v as { type?: string })?.type === 'REQUIRED')

function walk(qs: Q[] = [], out: F[] = []): F[] {
  for (const q of qs) { out.push(q.field); walk(q.field.repeatingSectionGrid, out) }
  return out
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

// shortcut: top-level items only (max 500, the API limit), one request per dictionary name per page load.
const dictCache = new Map<string, Promise<string[] | null>>()
function dictionary(name: string) {
  if (!dictCache.has(name)) {
    dictCache.set(name, fetch(`/api/v1/dictionaries/${encodeURIComponent(name)}?limit=500`, {
      headers: { Authorization: `Bearer ${import.meta.env.VITE_API_TOKEN ?? ''}` },
    }).then((r) => (r.ok ? r.json() : null)).then((d) => d?.items?.map((i: { name: string }) => i.name) ?? null).catch(() => null))
  }
  return dictCache.get(name)!
}

export default function Preview({ form, review }: { form: { tabs?: unknown }; review: Review }) {
  const tabs = (form.tabs ?? []) as Tab[]
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
    const all = ((form.tabs ?? []) as Tab[]).flatMap((t) => instances(t.questions, copies))
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
  const step = Math.max(0, visible.findIndex((t) => t.id === tabId) >= 0 ? visible.findIndex((t) => t.id === tabId)
    : visible.filter((t) => tabs.indexOf(t) < at).length - 1)
  const setStep = (i: number) => setTabId(visible[i].id)
  const tab = visible[step]
  if (!tab) return <p className="text-sm">Formularz nie ma widocznych stron.</p>
  const set = (id: string, v: Answer) => setAnswers((a) => ({ ...a, [id]: v }))
  const ctx: Ctx = { answers, set, hidden, review, copies, setCopies: (id, n) => setCopies((c) => ({ ...c, [id]: n })) }

  return (
    <div className="space-y-4 rounded border border-slate-200 p-4">
      <ol className="flex flex-wrap gap-2 text-sm">
        {visible.map((t, i) => (
          <li key={t.id}>
            <button type="button" onClick={() => setStep(i)} aria-current={i === step ? 'step' : undefined}
              className={`rounded-full border px-3 py-1 ${i === step ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300'}`}>
              {i + 1}. {t.title}
            </button>
          </li>
        ))}
      </ol>
      <h3 className="text-lg font-semibold">{tab.title}</h3>
      <Grid qs={tab.questions} ctx={ctx} suffix="" />
      <div className="flex justify-between">
        <button type="button" disabled={step === 0} onClick={() => setStep(step - 1)} className="rounded border px-3 py-1 disabled:opacity-40">Wstecz</button>
        <button type="button" disabled={step === visible.length - 1} onClick={() => setStep(step + 1)} className="rounded border px-3 py-1 disabled:opacity-40">Dalej</button>
      </div>
    </div>
  )
}

type Ctx = {
  answers: Record<string, Answer>; set: (id: string, v: Answer) => void; hidden: Set<string>; review: Review
  copies: Record<string, number>; setCopies: (id: string, n: number) => void
}

// Layout by x/cols on a grid as wide as the widest row (3 in the reference forms).
function Grid({ qs, ctx, suffix }: { qs: Q[]; ctx: Ctx; suffix: string }) {
  const width = Math.max(1, ...qs.map((q) => q.x + q.cols))
  return (
    <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${width}, minmax(0, 1fr))` }}>
      {/* rows flow in y, x order instead of fixed y, so hidden fields leave no gaps */}
      {qs.filter((q) => shown(q.field, suffix, ctx.hidden)).sort((a, b) => a.y - b.y || a.x - b.x).map((q) => (
        <div key={q.field.id} style={{ gridColumn: `${q.x + 1} / span ${q.cols}` }}>
          <Field f={q.field} ctx={ctx} suffix={suffix} />
        </div>
      ))}
    </div>
  )
}

function Label({ f, ctx, htmlFor }: { f: F; ctx: Ctx; htmlFor?: string }) {
  const why = ctx.review.get(f.id) ?? (f.techName ? ctx.review.get(f.techName) : undefined)
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium">
      {f.title}
      {required(f) && <span className="text-red-700" title="pole wymagane"> *</span>}
      {why && <span className="ml-1 cursor-help text-amber-600" title={`do przejrzenia: ${why}`} aria-label={`do przejrzenia: ${why}`}>⚑</span>}
      {f.tooltipMessage && <span className="ml-1 cursor-help text-slate-400" title={f.tooltipMessage}>ⓘ</span>}
    </label>
  )
}

const input = 'w-full rounded border border-slate-300 px-2 py-1.5 text-sm disabled:bg-slate-100'

function Field({ f, ctx, suffix }: { f: F; ctx: Ctx; suffix: string }) {
  const key = f.id + suffix // answers of repeated copies are kept apart
  const value = ctx.answers[key] ?? f.defaultValue ?? ''
  const one = Array.isArray(value) ? value[0] ?? '' : value // defaultValue may be a list, e.g. ["Polska"]
  const hint = text(f.description)
  const common = { id: key, disabled: f.readOnly, className: input }
  switch (f.type) {
    case 'SECTION':
      return (
        <fieldset className="rounded border border-slate-200 p-3">
          <legend className="px-1 font-semibold">{f.title}</legend>
          {hint && <p className="mb-2 text-sm text-slate-600">{hint}</p>}
          <Grid qs={f.repeatingSectionGrid ?? []} ctx={ctx} suffix={suffix} />
        </fieldset>
      )
    case 'REPEATING_SECTION':
      return <Repeating f={f} ctx={ctx} />
    case 'TEXT_BLOCK':
      return <p className="text-sm text-slate-700">{hint || f.title}</p>
    case 'CONSENT_SECTION':
      return (
        <div className="space-y-2">
          <Label f={f} ctx={ctx} />
          {(f.consentSectionConfig?.consents ?? []).map((c, i) => (
            <label key={i} className="flex gap-2 text-sm"><input type="checkbox" />{text(c.description)}</label>
          ))}
        </div>
      )
    case 'TEXTAREA':
      return <div><Label f={f} ctx={ctx} htmlFor={key} /><textarea {...common} rows={3} value={one} onChange={(e) => ctx.set(key, e.target.value)} /></div>
    case 'DATEPICKER':
      return <div><Label f={f} ctx={ctx} htmlFor={key} /><input {...common} type="date" value={one} onChange={(e) => ctx.set(key, e.target.value)} /></div>
    case 'NUMBER':
      return <div><Label f={f} ctx={ctx} htmlFor={key} /><input {...common} type="number" value={one} onChange={(e) => ctx.set(key, e.target.value)} /></div>
    case 'FILE_UPLOADER':
      return <div><Label f={f} ctx={ctx} htmlFor={key} /><input {...common} type="file" /></div>
    case 'SELECT':
      return <div><Label f={f} ctx={ctx} htmlFor={key} /><Select f={f} id={key} value={one} onChange={(v) => ctx.set(key, v)} /></div>
    case 'RADIO':
    case 'CHECKBOX': {
      const multi = f.type === 'CHECKBOX'
      const chosen = ([] as string[]).concat(value || [])
      return (
        <fieldset>
          <legend><Label f={f} ctx={ctx} /></legend>
          {(f.options ?? []).map((o) => (
            <label key={o.id} className="mr-4 inline-flex items-center gap-1 text-sm">
              <input type={multi ? 'checkbox' : 'radio'} name={key} disabled={f.readOnly} checked={chosen.includes(o.name)}
                onChange={(e) => ctx.set(key, multi ? (e.target.checked ? [...chosen, o.name] : chosen.filter((c) => c !== o.name)) : o.name)} />
              {o.name}
            </label>
          ))}
        </fieldset>
      )
    }
    default: // TEXT_FIELD and anything unknown
      return <div><Label f={f} ctx={ctx} htmlFor={key} /><input {...common} value={one} onChange={(e) => ctx.set(key, e.target.value)} />{f.type !== 'TEXT_FIELD' && <p className="text-xs text-slate-500">typ {f.type}</p>}</div>
  }
}

function Select({ f, id, value, onChange }: { f: F; id: string; value: string; onChange: (v: string) => void }) {
  const [items, setItems] = useState<string[] | null | undefined>(f.dictionaryName ? undefined : (f.options ?? []).map((o) => o.name))
  useEffect(() => { if (f.dictionaryName) dictionary(f.dictionaryName).then(setItems) }, [f.dictionaryName])
  const placeholder = items === undefined ? 'wczytuję słownik…' : items === null ? `słownik ${f.dictionaryName} niedostępny` : 'wybierz'
  return (
    <select id={id} disabled={f.readOnly} value={value} onChange={(e) => onChange(e.target.value)} className={input}>
      <option value="">— {placeholder} —</option>
      {(items ?? []).map((n, i) => <option key={i} value={n}>{n}</option>)}
    </select>
  )
}

function Repeating({ f, ctx }: { f: F; ctx: Ctx }) {
  const copies = ctx.copies[f.id] ?? 1
  return (
    <fieldset className="space-y-3 rounded border border-slate-200 p-3">
      <legend className="px-1 font-semibold">{f.title}</legend>
      {Array.from({ length: copies }, (_, i) => (
        <div key={i} className={i ? 'border-t border-dashed border-slate-300 pt-3' : ''}>
          {copies > 1 && <p className="mb-2 text-xs text-slate-500">#{i + 1}</p>}
          <Grid qs={f.repeatingSectionGrid ?? []} ctx={ctx} suffix={i ? `#${i}` : ''} />
        </div>
      ))}
      <button type="button" onClick={() => ctx.setCopies(f.id, copies + 1)} className="rounded border px-3 py-1 text-sm">+ dodaj</button>
    </fieldset>
  )
}
