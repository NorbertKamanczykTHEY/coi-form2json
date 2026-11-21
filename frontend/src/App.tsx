import { useEffect, useState } from 'react'
import type { components } from './api'

// /api/v1/info has no response schema in OpenAPI yet, so its shape is declared here.
type Info = {
  version: string
  limits: { extensions: string[]; forbidden_filename_chars: string; max_file_mb: number; max_filename_len: number }
}
type Form = components['schemas']['Form']
// editor.proposals is not described in OpenAPI yet (ADR 0025): {dictionary, fieldIds, changes}.
type Proposal = { dictionary: components['schemas']['Proposal']; fieldIds: string[]; changes: Record<string, Record<string, unknown>> }
type Envelope = { id: string; form: Form; report: unknown; editor?: { proposals?: Proposal[] } }
type Accept = { busy?: boolean; done?: boolean; error?: string }
type Job = {
  key: string; name: string; status: 'pending' | 'running' | 'done' | 'error'; log: string[]
  result?: Envelope; error?: string; accepted?: Record<string, Accept>
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
              <p className="text-sm">Id formularza: <code>{j.result.id}</code></p>
              <Block title="JSON COI" value={j.result.form} />
              <Block title="Raport" value={j.result.report} />
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
