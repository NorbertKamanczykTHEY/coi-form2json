import { useEffect, useState } from 'react'
import type { components } from './api'
import Preview, { type Review } from './Preview'

// /api/v1/info has no response schema in OpenAPI yet, so its shape is declared here.
type Info = {
  version: string
  limits: { extensions: string[]; forbidden_filename_chars: string; max_file_mb: number; max_filename_len: number }
}
type Form = components['schemas']['Form']
// editor.proposals is not described in OpenAPI yet (ADR 0025): {dictionary, fieldIds, changes}.
type Proposal = { dictionary: components['schemas']['Proposal']; fieldIds: string[]; changes: Record<string, Record<string, unknown>> }
type Envelope = {
  id: string; form: Form; report: { needs_review?: { key?: string; field_id?: string; why?: string }[] } | null
  editor?: {
    proposals?: Proposal[]; field_map?: Record<string, { needs_review?: boolean; doubt?: string | null }>
    applicant_self_only?: { value: boolean; source: 'dokument' | 'domyślnie' | 'edytor'; quote: string | null }
  }
}
type Accept = { busy?: boolean; done?: boolean; error?: string }
type Job = {
  key: string; name: string; status: 'pending' | 'running' | 'done' | 'error'; log: string[]
  result?: Envelope; error?: string; accepted?: Record<string, Accept>; preview?: boolean
}

// Fields to flag in the preview: report.needs_review (by field id or techName) and editor.field_map[id].needs_review.
function review(r: Envelope): Review {
  const m: Review = new Map()
  for (const n of r.report?.needs_review ?? []) for (const k of [n.field_id, n.key]) if (k) m.set(k, n.why ?? 'do przejrzenia')
  for (const [id, f] of Object.entries(r.editor?.field_map ?? {})) if (f.needs_review && !m.has(id)) m.set(id, f.doubt ?? 'do przejrzenia')
  return m
}

// shortcut: the token is baked into the bundle (VITE_API_TOKEN), demo only; replace with a real login/IdP before deployment.
const auth = { Authorization: `Bearer ${import.meta.env.VITE_API_TOKEN ?? ''}` }

// At most `limit` uploads run at once; the rest wait in FIFO order.
const limit = Math.max(1, Number(import.meta.env.VITE_BATCH_CONCURRENCY) || 3)
let active = 0
const waiting: (() => void)[] = []
async function withSlot(fn: () => Promise<void>) {
  if (active < limit) active++
  else await new Promise<void>((r) => waiting.push(r)) // slot handed over by a finishing upload
  try {
    await fn()
  } finally {
    const next = waiting.shift()
    if (next) next()
    else active--
  }
}

function checkFile(f: File, info: Info | null): string | null {
  if (!info) return null
  const l = info.limits
  const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
  if (!l.extensions.includes(ext)) return `rozszerzenie .${ext} nieobsługiwane (${l.extensions.join(', ')})`
  if (f.size > l.max_file_mb * 1024 * 1024) return `plik większy niż ${l.max_file_mb} MB`
  if (f.name.length > l.max_filename_len) return `nazwa dłuższa niż ${l.max_filename_len} znaków`
  const bad = [...l.forbidden_filename_chars].filter((c) => f.name.includes(c))
  if (bad.length) return `niedozwolone znaki w nazwie: ${bad.join(' ')}`
  return null
}

function describe(event: string, data: string): string {
  try {
    const d = JSON.parse(data)
    if (event === 'stage') return `${d.stage}: ${d.status}${d.seconds != null ? ` (${d.seconds} s)` : ''}${d.parser ? `, ${d.parser}` : ''}`
    if (event === 'error') return `błąd ${d.status ?? ''}: ${d.detail ?? d.title ?? data}`
    return `${event}: ${data}`
  } catch {
    return `${event}: ${data}`
  }
}

// Readable message from an RFC 9457 problem+json (or any) error response.
async function problem(res: Response): Promise<string> {
  const t = await res.text()
  try {
    const p = JSON.parse(t)
    const errors = Array.isArray(p.errors) ? p.errors.map((e: { path?: string; message?: string }) => `${e.path ?? ''}: ${e.message ?? ''}`) : []
    return [`HTTP ${res.status} ${p.title ?? ''}${p.detail ? `: ${typeof p.detail === 'string' ? p.detail : JSON.stringify(p.detail)}` : ''}`, ...errors].join('\n')
  } catch {
    return `HTTP ${res.status}: ${t}`
  }
}

// Copy of the form with every field whose id is in `changes` overwritten by its change.
function applyChanges(form: Form, changes: Proposal['changes']): Form {
  const copy = structuredClone(form)
  for (const f of fields(copy)) if (changes[f.id]) Object.assign(f, changes[f.id])
  return copy
}

// All fields of a form, nested ones (repeatingSectionGrid) included; same objects, not copies.
type Field = { id: string; techName?: string; title?: string; type?: string; repeatingSectionGrid?: { field: Field }[] }
function fields(form: Form): Field[] {
  const out: Field[] = []
  const walk = (qs: { field: Field }[] = []) => qs.forEach((q) => { out.push(q.field); walk(q.field.repeatingSectionGrid) })
  ;(form.tabs as { questions: { field: Field }[] }[] | undefined)?.forEach((t) => walk(t.questions))
  return out
}

// Accept a dictionary proposal: create it, then PUT the form with the proposal's field changes. Returns the saved form.
async function acceptProposal(id: string, form: Form, p: Proposal): Promise<Form> {
  const json = { ...auth, 'Content-Type': 'application/json' }
  const created = await fetch('/api/v1/dictionaries/from-proposal', { method: 'POST', headers: json, body: JSON.stringify(p.dictionary) })
  // 409 also means "id taken": fine if that dictionary already exists (accepted earlier, e.g. from another file in the batch).
  if (!created.ok) {
    const exists = created.status === 409 && (await fetch(`/api/v1/dictionaries/${encodeURIComponent(p.dictionary.id)}`, { headers: auth })).ok
    if (!exists) throw new Error(`Słownik: ${await problem(created)}`)
  }
  const changes = Object.fromEntries(p.fieldIds.map((f) => [f, p.changes[f]]).filter(([, c]) => c))
  const saved = await fetch(`/api/v1/forms/${id}`, { method: 'PUT', headers: json, body: JSON.stringify(applyChanges(form, changes)) })
  if (!saved.ok) throw new Error(`Zapis formularza: ${await problem(saved)}`)
  return saved.json()
}

// Rebuild a stored form with applicant_self_only (ADR 0027); the server saves it, replacing manual edits.
async function regenerate(id: string, selfOnly: boolean): Promise<Envelope> {
  const body: components['schemas']['Regenerate'] = { applicant_self_only: selfOnly }
  const res = await fetch(`/api/v1/forms/${id}/regenerate?report=true&editor=true`, {
    method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (res.status === 409) {
    const p = await res.clone().json().catch(() => ({}))
    if (p.code === 'no_stored_tree') throw new Error('Ten formularz powstał przed tą funkcją. Wczytaj plik ponownie, żeby móc go przebudować.')
  }
  if (!res.ok) throw new Error(await problem(res))
  return res.json()
}

// "Only in person" switch: confirms inline, then regenerates and hands the new envelope back.
function SelfOnly({ r, onDone }: { r: Envelope; onDone: (e: Envelope) => void }) {
  const [ask, setAsk] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const s = r.editor?.applicant_self_only
  if (!r.id || !s) return null
  const from = s.source === 'dokument' ? `z dokumentu${s.quote ? `: „${s.quote}”` : ''}` : s.source === 'edytor' ? 'ustawione w edytorze' : 'domyślnie'
  async function go() {
    setBusy(true); setError('')
    try { onDone(await regenerate(r.id, !s!.value)); setAsk(false) } catch (e) { setError(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-2 rounded border border-slate-200 p-3 text-sm">
      <label className="flex items-center gap-2 font-medium">
        <input type="checkbox" checked={s.value} disabled={busy || ask} onChange={() => setAsk(true)} />
        Wniosek tylko osobiście (bez pełnomocnika)
      </label>
      <p className="text-slate-600">Źródło: {from}</p>
      {ask && (
        <div className="flex flex-wrap items-center gap-2 rounded bg-amber-50 p-2" role="alert">
          <span>Zmiana przebuduje formularz i usunie ręczne poprawki. Kontynuuj?</span>
          <button type="button" disabled={busy} onClick={go} className="rounded bg-slate-900 px-3 py-1 text-white disabled:opacity-50">{busy ? 'Przebudowuję…' : 'Tak, przebuduj'}</button>
          <button type="button" disabled={busy} onClick={() => setAsk(false)} className="rounded border px-3 py-1">Anuluj</button>
        </div>
      )}
      {error && <pre className="whitespace-pre-wrap text-red-700">{error}</pre>}
    </div>
  )
}

// POST /api/v1/forms?report=true&editor=true with Accept: text/event-stream; parses the SSE frames from the fetch body.
async function upload(file: File, update: (p: Partial<Job>, line?: string) => void) {
  const body = new FormData()
  body.append('file', file)
  const res = await fetch('/api/v1/forms?report=true&editor=true', { method: 'POST', headers: { ...auth, Accept: 'text/event-stream' }, body })
  if (!res.ok || !res.body) return update({ status: 'error', error: await problem(res) })
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buf = ''
  let finished = false
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += value.replace(/\r\n/g, '\n')
    let i
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const frame = buf.slice(0, i)
      buf = buf.slice(i + 2)
      let event = 'message'
      const data: string[] = []
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
      }
      const text = data.join('\n')
      if (event === 'result') {
        finished = true
        update({ status: 'done', result: JSON.parse(text) }, 'result: gotowe')
      } else if (event === 'error') {
        finished = true
        update({ status: 'error', error: describe(event, text) }, describe(event, text))
      } else update({}, describe(event, text))
    }
  }
  if (!finished) update({ status: 'error', error: 'strumień zakończył się bez wyniku' })
}

export default function App() {
  const [info, setInfo] = useState<Info | null>(null)
  const [infoError, setInfoError] = useState('')
  const [jobs, setJobs] = useState<Job[]>([])

  useEffect(() => {
    fetch('/api/v1/info')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setInfo)
      .catch((e) => setInfoError(String(e)))
  }, [])

  function start(files: FileList | null) {
    for (const file of Array.from(files ?? [])) {
      const key = crypto.randomUUID()
      const invalid = checkFile(file, info)
      setJobs((js) => [{ key, name: file.name, status: invalid ? 'error' : 'pending', log: [], error: invalid ?? undefined }, ...js])
      if (invalid) continue
      const update = (p: Partial<Job>, line?: string) =>
        setJobs((js) => js.map((j) => (j.key === key ? { ...j, ...p, log: line ? [...j.log, line] : j.log } : j)))
      withSlot(() => {
        update({ status: 'running' })
        return upload(file, update).catch((e) => update({ status: 'error', error: String(e) }))
      })
    }
  }

  // A COI JSON file (e.g. the reference forms #1/#5) or a saved {id, form, report} envelope, opened for preview only.
  async function open(files: FileList | null) {
    for (const file of Array.from(files ?? [])) {
      const key = crypto.randomUUID()
      try {
        const d = JSON.parse(await file.text())
        const result: Envelope = d.form ? d : { id: '', form: d, report: null }
        setJobs((js) => [{ key, name: file.name, status: 'done', log: [], result, preview: true }, ...js])
      } catch (e) {
        setJobs((js) => [{ key, name: file.name, status: 'error', log: [], error: `To nie jest JSON: ${e}` }, ...js])
      }
    }
  }

  async function accept(job: Job, p: Proposal) {
    const did = p.dictionary.id
    const mark = (a: Accept, form?: Form) => setJobs((js) => js.map((j) => (j.key !== job.key || !j.result ? j : {
      ...j, accepted: { ...j.accepted, [did]: a }, result: form ? { ...j.result, form } : j.result,
    })))
    mark({ busy: true })
    try {
      // shortcut: uses the form from the render that was clicked; accepting two proposals of one file at the same time would race
      mark({ done: true }, await acceptProposal(job.result!.id, job.result!.form, p))
    } catch (e) {
      mark({ error: e instanceof Error ? e.message : String(e) })
    }
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-4 font-sans text-slate-900">
      <h1 className="text-2xl font-semibold">COI: import formularza</h1>

      <section className="space-y-2 rounded-lg border border-slate-300 p-4">
        <label className="block font-medium" htmlFor="files">Pliki formularzy (można wybrać kilka)</label>
        <input id="files" type="file" multiple accept={info?.limits.extensions.map((e) => `.${e}`).join(',')}
          onChange={(e) => { start(e.target.files); e.target.value = '' }}
          className="block w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-white" />
        <label className="block pt-2 text-sm font-medium" htmlFor="json">Albo otwórz gotowy JSON COI do podglądu</label>
        <input id="json" type="file" multiple accept=".json,application/json" onChange={(e) => { open(e.target.files); e.target.value = '' }}
          className="block w-full text-sm file:mr-3 file:rounded file:border file:border-slate-300 file:bg-white file:px-3 file:py-1" />
        <p className="text-sm text-slate-600">
          {info
            ? `Limity: ${info.limits.extensions.join(', ')} · do ${info.limits.max_file_mb} MB · nazwa do ${info.limits.max_filename_len} znaków · API ${info.version}`
            : infoError ? `Nie udało się pobrać /api/v1/info: ${infoError}` : 'Pobieram limity…'}
        </p>
      </section>

      {jobs.map((j) => (
        <section key={j.key} className="space-y-3 rounded-lg border border-slate-300 p-4" aria-live="polite">
          <h2 className="font-medium">
            {j.name}{' '}
            <span className={{ pending: 'text-slate-500', running: 'text-amber-700', done: 'text-green-700', error: 'text-red-700' }[j.status]}>
              {{ pending: 'w kolejce', running: 'przetwarzanie…', done: 'gotowe', error: 'błąd' }[j.status]}
            </span>
          </h2>
          {j.error && <p className="text-sm text-red-700">{j.error}</p>}
          {j.log.length > 0 && <ol className="list-decimal pl-6 font-mono text-xs text-slate-700">{j.log.map((l, i) => <li key={i}>{l}</li>)}</ol>}
          {j.result && (
            <>
              {j.result.id && <p className="text-sm">Id formularza: <code>{j.result.id}</code></p>}
              <SelfOnly r={j.result} onDone={(e) => setJobs((js) => js.map((x) => (x.key === j.key ? { ...x, result: e, accepted: {} } : x)))} />
              <div className="flex gap-1 text-sm" role="group" aria-label="Widok wyniku">
                {([[false, 'JSON i raport'], [true, 'Podgląd']] as const).map(([v, label]) => (
                  <button key={label} type="button" aria-pressed={!!j.preview === v}
                    onClick={() => setJobs((js) => js.map((x) => (x.key === j.key ? { ...x, preview: v } : x)))}
                    className={`rounded border px-3 py-1 ${!!j.preview === v ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300'}`}>{label}</button>
                ))}
              </div>
              {j.preview
                ? <Preview form={j.result.form} review={review(j.result)} />
                : <><Block title="JSON COI" value={j.result.form} />{j.result.report && <Block title="Raport" value={j.result.report} />}</>}
              {(j.result.editor?.proposals ?? []).map((p) => {
                const a = j.accepted?.[p.dictionary.id] ?? {}
                const byId = new Map(fields(j.result!.form).map((f) => [f.id, f]))
                return (
                  <div key={p.dictionary.id} className="space-y-1 rounded border border-slate-200 p-3 text-sm">
                    <p className="font-medium">Proponowany słownik: {p.dictionary.name} <code className="text-slate-600">({p.dictionary.id})</code></p>
                    <p>Pozycje ({p.dictionary.items.length}): {p.dictionary.items.slice(0, 5).map((i) => (i as { name?: string }).name ?? JSON.stringify(i)).join(', ')}{p.dictionary.items.length > 5 ? ', …' : ''}</p>
                    <p>Pola: {p.fieldIds.map((id) => { const f = byId.get(id); return f ? `${f.title ?? f.techName} (${f.type})` : id }).join(', ')}</p>
                    {a.done
                      ? <p className="text-green-700">Słownik przyjęty, formularz zapisany.</p>
                      : <button type="button" disabled={a.busy} onClick={() => accept(j, p)}
                          className="rounded bg-slate-900 px-3 py-1.5 text-white disabled:opacity-50">{a.busy ? 'Zapisuję…' : 'Akceptuj słownik'}</button>}
                    {a.error && <pre className="whitespace-pre-wrap text-red-700">{a.error}</pre>}
                  </div>
                )
              })}
            </>
          )}
        </section>
      ))}
    </main>
  )
}

function Block({ title, value }: { title: string; value: unknown }) {
  return (
    <details open className="rounded border border-slate-200">
      <summary className="cursor-pointer bg-slate-50 px-3 py-1 text-sm font-medium">{title}</summary>
      <pre className="max-h-96 overflow-auto p-3 text-xs">{JSON.stringify(value, null, 2)}</pre>
    </details>
  )
}
