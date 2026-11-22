import { useSyncExternalStore } from 'react'
import { IMPORT_CONCURRENCY } from '@/config'
import { auth, problem, type Envelope, type Info } from './api'
import { plural } from './plural'

// Import queue: lives outside React so it keeps running when the import dialog is closed.
export type LogEntry =
  | { kind: 'stage'; stage: string; status: string; seconds?: number; parser?: string; cost?: number; fields?: number; at: number }
  | { kind: 'escalation'; step?: string; model?: string; accepted?: boolean; error?: string | null; page?: number; at: number }
  | { kind: 'warning'; message: string; at: number }
  | { kind: 'result'; id: string; cost?: number; seconds?: number; review: number; at: number }
  | { kind: 'error'; message: string; at: number }
export type Job = {
  key: string; name: string; size: number; status: 'waiting' | 'running' | 'done' | 'rejected'
  reason?: string; log: LogEntry[]; id?: string; started?: number; ended?: number
}

let jobs: Job[] = []
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())
function patch(key: string, f: (j: Job) => Partial<Job>) {
  jobs = jobs.map((j) => (j.key === key ? { ...j, ...f(j) } : j))
  emit()
}

// Ids of forms imported in this browser tab: the project list marks them "nowe".
const FRESH = 'coi.fresh'
export const fresh = (): Set<string> => {
  try { return new Set(JSON.parse(sessionStorage.getItem(FRESH) ?? '[]')) } catch { return new Set() }
}
function addFresh(id: string) {
  try { sessionStorage.setItem(FRESH, JSON.stringify([...fresh(), id])) } catch { /* private mode: the badge just won't survive a reload */ }
}

const active = () => jobs.some((j) => j.status === 'waiting' || j.status === 'running')
// Leaving the page would drop uploads in flight (the server keeps only finished results).
window.addEventListener('beforeunload', (e) => { if (active()) e.preventDefault() })

export function check(f: File, info: Info | null): string | null {
  if (!info) return null
  const l = info.limits
  const ext = f.name.includes('.') ? f.name.split('.').pop()!.toLowerCase() : ''
  if (!l.extensions.includes(ext)) return `Nieobsługiwany typ pliku${ext ? ` .${ext}` : ''}. Dozwolone: ${l.extensions.join(', ')}.`
  if (f.name.length > l.max_filename_len) return `Nazwa pliku ma ${plural(f.name.length, 'znak', 'znaki', 'znaków')}, limit to ${l.max_filename_len}.`
  const bad = [...new Set([...l.forbidden_filename_chars].filter((c) => f.name.includes(c)))]
  if (bad.length) return `Nazwa zawiera niedozwolone znaki: ${bad.join(' ')}`
  if (f.size > l.max_file_mb * 2 ** 20) return `Plik ma ${(f.size / 2 ** 20).toFixed(1)} MB, limit to ${l.max_file_mb} MB.`
  if (f.size === 0) return 'Plik jest pusty.'
  return null
}

const waiting: [string, File][] = []
let running = 0
function pump() {
  while (running < IMPORT_CONCURRENCY && waiting.length) {
    const [key, file] = waiting.shift()!
    running++
    patch(key, () => ({ status: 'running', started: Date.now() }))
    upload(key, file)
      .catch((e) => fail(key, e instanceof Error ? e.message : String(e)))
      .finally(() => { running--; pump() })
  }
}
const fail = (key: string, reason: string) =>
  patch(key, (j) => ({ status: 'rejected', reason, ended: Date.now(), log: [...j.log, { kind: 'error', message: reason, at: Date.now() }] }))

export function enqueue(files: File[], info: Info | null) {
  for (const file of files) {
    const key = crypto.randomUUID()
    const reason = check(file, info)
    jobs = [...jobs, { key, name: file.name, size: file.size, status: reason ? 'rejected' : 'waiting', reason: reason ?? undefined, log: [] }]
    if (!reason) waiting.push([key, file])
  }
  emit()
  pump()
}
export function clearFinished() {
  jobs = jobs.filter((j) => j.status === 'waiting' || j.status === 'running')
  emit()
}

const listeners2 = (l: () => void) => { listeners.add(l); return () => { listeners.delete(l) } }
export const useQueue = () => useSyncExternalStore(listeners2, () => jobs)

// POST /api/v1/forms with Accept: text/event-stream; SSE frames are parsed from the fetch body.
async function upload(key: string, file: File) {
  const body = new FormData()
  body.append('file', file)
  const res = await fetch('/api/v1/forms?report=true', { method: 'POST', headers: { ...auth(), Accept: 'text/event-stream' }, body })
  if (!res.ok || !res.body) return fail(key, rejectReason(res.status, (await problem(res)).message))
  const add = (e: LogEntry) => patch(key, (j) => ({ log: [...j.log, e] }))
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buf = ''
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
      let d
      try { d = JSON.parse(data.join('\n')) } catch { continue }
      const at = Date.now()
      if (event === 'stage') add({ kind: 'stage', ...d, at })
      else if (event === 'escalation') add({ kind: 'escalation', ...d, at })
      else if (event === 'warning') add({ kind: 'warning', message: d.message ?? String(d), at })
      else if (event === 'error') return fail(key, rejectReason(d.status, d.detail ?? d.title))
      else if (event === 'result') {
        const env = d as Envelope
        addFresh(env.id)
        add({ kind: 'result', id: env.id, cost: env.report?.cost, seconds: env.report?.seconds, review: env.report?.needs_review?.length ?? 0, at })
        patch(key, () => ({ status: 'done', id: env.id, ended: at }))
        return
      }
    }
  }
  fail(key, 'Połączenie zakończyło się bez wyniku. Spróbuj ponownie.')
}

const REASON: Record<number, string> = {
  400: 'Serwer odrzucił plik (nazwa lub zawartość żądania)', 401: 'Brak dostępu: token jest nieważny albo wygasł',
  413: 'Plik jest za duży', 415: 'Typ pliku nie zgadza się z rozszerzeniem albo nie jest obsługiwany', 422: 'Nie da się odczytać pliku',
  502: 'Błąd modelu językowego', 504: 'Model językowy nie odpowiedział na czas',
}
const rejectReason = (status: number, detail?: string) => `${REASON[status] ?? `Błąd serwera (${status})`}${detail ? `: ${detail}` : ''}`
