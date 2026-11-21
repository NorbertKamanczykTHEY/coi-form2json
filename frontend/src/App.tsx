import { useEffect, useState } from 'react'
import type { components } from './api'

// /api/v1/info has no response schema in OpenAPI yet, so its shape is declared here.
type Info = {
  version: string
  limits: { extensions: string[]; forbidden_filename_chars: string; max_file_mb: number; max_filename_len: number }
}
type Envelope = { id: string; form: components['schemas']['Form']; report: unknown }
type Job = { key: string; name: string; status: 'pending' | 'running' | 'done' | 'error'; log: string[]; result?: Envelope; error?: string }

// shortcut: the token is baked into the bundle (VITE_API_TOKEN), demo only; replace with a real login/IdP before deployment.
const auth = { Authorization: `Bearer ${import.meta.env.VITE_API_TOKEN ?? ''}` }

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

// POST /api/v1/forms?report=true with Accept: text/event-stream; parses the SSE frames from the fetch body.
async function upload(file: File, update: (p: Partial<Job>, line?: string) => void) {
  const body = new FormData()
  body.append('file', file)
  const res = await fetch('/api/v1/forms?report=true', { method: 'POST', headers: { ...auth, Accept: 'text/event-stream' }, body })
  if (!res.ok || !res.body) {
    const t = await res.text()
    let msg = t
    try { const p = JSON.parse(t); msg = p.detail ?? p.title ?? t } catch { /* not problem+json */ }
    return update({ status: 'error', error: `HTTP ${res.status}: ${msg}` })
  }
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
      setJobs((js) => [{ key, name: file.name, status: invalid ? 'error' : 'running', log: [], error: invalid ?? undefined }, ...js])
      if (invalid) continue
      const update = (p: Partial<Job>, line?: string) =>
        setJobs((js) => js.map((j) => (j.key === key ? { ...j, ...p, log: line ? [...j.log, line] : j.log } : j)))
      upload(file, update).catch((e) => update({ status: 'error', error: String(e) }))
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
