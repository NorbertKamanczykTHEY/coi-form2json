import type { components } from '@/api'

// /api/v1/info and GET /api/v1/forms have no response schema in OpenAPI yet, so their shapes are declared here.
export type Info = {
  version: string
  limits: { extensions: string[]; forbidden_filename_chars: string; max_file_mb: number; max_filename_len: number }
}
export type ListItem = {
  id: string; title: string; filename: string; created_at: string; updated_at: string | null
  needs_review: number; open_review: number; proposals: number
}
export type Form = components['schemas']['Form']
// editor.proposals is not described in OpenAPI yet (ADR 0025): {dictionary, fieldIds, changes}.
export type Proposal = { dictionary: components['schemas']['Proposal']; fieldIds: string[]; changes: Record<string, Record<string, unknown>> }
export type ReviewItem = { key?: string; field_id?: string | null; why?: string; fails?: string[] }
export type Report = { needs_review?: ReviewItem[]; warnings?: string[]; cost?: number; seconds?: number } | null
export type Envelope = {
  id: string; form: Form; report: Report
  editor?: {
    proposals?: Proposal[]; resolved?: string[]
    applicant_self_only?: { value: boolean; source: 'dokument' | 'domyślnie' | 'edytor'; quote: string | null }
  }
}

// ADR 0015: no login; the clerk pastes a JWT, kept for the browser tab only. No token is ever built into the bundle.
const KEY = 'coi.token'
export const token = {
  get: () => sessionStorage.getItem(KEY) ?? '',
  set: (t: string) => (t ? sessionStorage.setItem(KEY, t.trim()) : sessionStorage.removeItem(KEY)),
}
export const auth = (): Record<string, string> => ({ Authorization: `Bearer ${token.get()}` })
const json = () => ({ ...auth(), 'Content-Type': 'application/json' })

export class ApiError extends Error {
  status: number
  errors: { path?: string; message?: string }[]
  constructor(status: number, message: string, errors: { path?: string; message?: string }[] = []) {
    super(message)
    this.status = status
    this.errors = errors
  }
}

// RFC 9457 problem+json (or any error body) -> ApiError with a readable message.
export async function problem(res: Response): Promise<ApiError> {
  const t = await res.text()
  try {
    const p = JSON.parse(t)
    const detail = typeof p.detail === 'string' ? p.detail : p.detail ? JSON.stringify(p.detail) : p.title
    return new ApiError(res.status, detail || `HTTP ${res.status}`, Array.isArray(p.errors) ? p.errors : [])
  } catch {
    return new ApiError(res.status, `HTTP ${res.status}${t ? `: ${t.slice(0, 200)}` : ''}`)
  }
}

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) throw await problem(res)
  return res.status === 204 ? (undefined as T) : res.json()
}

export const api = {
  info: () => call<Info>('/api/v1/info'),
  list: () => call<{ items: ListItem[] }>('/api/v1/forms', { headers: auth() }).then((r) => r.items),
  get: (id: string) => call<Envelope>(`/api/v1/forms/${id}?report=true&editor=true`, { headers: auth() }),
  remove: (id: string) => call<void>(`/api/v1/forms/${id}`, { method: 'DELETE', headers: auth() }),
  save: (id: string, form: Form) => call<Form>(`/api/v1/forms/${id}`, { method: 'PUT', headers: json(), body: JSON.stringify(form) }),
  resolve: (id: string, resolved: string[]) =>
    call<{ resolved: string[] }>(`/api/v1/forms/${id}/resolved`, { method: 'PUT', headers: json(), body: JSON.stringify({ resolved }) }),
  regenerate: (id: string, selfOnly: boolean) =>
    call<Envelope>(`/api/v1/forms/${id}/regenerate?report=true&editor=true`, {
      method: 'POST', headers: json(), body: JSON.stringify({ applicant_self_only: selfOnly } satisfies components['schemas']['Regenerate']),
    }),
  // 409 also means "id taken": fine if that dictionary already exists (accepted earlier, e.g. from another file).
  async createDictionary(d: Proposal['dictionary']) {
    const res = await fetch('/api/v1/dictionaries/from-proposal', { method: 'POST', headers: json(), body: JSON.stringify(d) })
    if (res.ok) return
    if (res.status === 409 && (await fetch(`/api/v1/dictionaries/${encodeURIComponent(d.id)}`, { headers: auth() })).ok) return
    throw await problem(res)
  },
  validate: (form: unknown) =>
    call<{ valid: boolean; errors: { path: string; message: string }[] }>('/api/v1/forms/validate', { method: 'POST', headers: json(), body: JSON.stringify(form) }),
}

// shortcut: top-level items only (max 500, the API limit), one request per dictionary name per page load.
const dictCache = new Map<string, Promise<string[] | null>>()
export function dictionaryItems(name: string) {
  if (!dictCache.has(name)) {
    dictCache.set(name, fetch(`/api/v1/dictionaries/${encodeURIComponent(name)}?limit=500`, { headers: auth() })
      .then((r) => (r.ok ? r.json() : null)).then((d) => d?.items?.map((i: { name: string }) => i.name) ?? null).catch(() => null))
  }
  return dictCache.get(name)!
}
