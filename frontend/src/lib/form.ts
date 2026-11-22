import type { Envelope, Form, Proposal, ReviewItem } from './api'

export type Q = { x: number; y: number; rows: number; cols: number; field: Field }
export type Field = {
  id: string; type: string; techName?: string; title?: string; description?: string; tooltipMessage?: string
  options?: { id: string; name: string }[]; validation?: unknown[]; dictionaryName?: string; readOnly?: boolean
  defaultValue?: string | string[]; repeatingSectionGrid?: Q[]; states?: { type: string; query: string }[]
  consentSectionConfig?: { consents?: { description?: string }[]; required?: boolean }
}
export type Tab = { id: string; title: string; type: string; questions: Q[] }

export const tabsOf = (form: Form) => ((form as { tabs?: Tab[] }).tabs ?? [])

// All fields under these questions, nested ones (SECTION, REPEATING_SECTION) included; same objects, not copies.
export function walk(qs: Q[] = [], out: Field[] = []): Field[] {
  for (const q of qs) { out.push(q.field); walk(q.field.repeatingSectionGrid, out) }
  return out
}
export const fieldsOf = (form: Form) => tabsOf(form).flatMap((t) => walk(t.questions))

// HTML from the form (descriptions, consents) as plain text: it comes from an LLM, so it never goes to innerHTML.
export const text = (html?: string) => (html ? new DOMParser().parseFromString(html, 'text/html').body.textContent?.trim() ?? '' : '')
// validation is a list in the schema, but reference #1 has `{}` in places
export const isRequired = (f: Field) => Array.isArray(f.validation) && f.validation.some((v) => v === 'REQUIRED' || (v as { type?: string })?.type === 'REQUIRED')
export function setRequired(f: Field, on: boolean) {
  const rest = (Array.isArray(f.validation) ? f.validation : []).filter((v) => v !== 'REQUIRED' && (v as { type?: string })?.type !== 'REQUIRED')
  f.validation = on ? ['REQUIRED', ...rest] : rest
}

// One review point: report.needs_review item, keyed like the API stores it (field_id, else key); `fieldId` resolves a key that is a techName.
export type Point = { key: string; why: string; fails: string[]; fieldId: string | null }
export const reviewKey = (n: ReviewItem) => n.field_id || n.key || ''
export function points(env: Envelope, form: Form): Point[] {
  const byTech = new Map(fieldsOf(form).filter((f) => f.techName).map((f) => [f.techName!, f.id]))
  const ids = new Set(fieldsOf(form).map((f) => f.id))
  return (env.report?.needs_review ?? []).filter(reviewKey).map((n) => ({
    key: reviewKey(n), why: n.why ?? 'Do sprawdzenia', fails: n.fails ?? [],
    fieldId: n.field_id && ids.has(n.field_id) ? n.field_id : (n.key && byTech.get(n.key)) || null,
  }))
}

// A proposal counts as accepted when every field it names already points at its dictionary.
export function accepted(form: Form, p: Proposal) {
  const byId = new Map(fieldsOf(form).map((f) => [f.id, f]))
  return p.fieldIds.every((id) => !p.changes[id] || byId.get(id)?.dictionaryName === p.dictionary.id)
}
export function applyProposal(form: Form, p: Proposal): Form {
  const copy = structuredClone(form)
  for (const f of fieldsOf(copy)) if (p.fieldIds.includes(f.id) && p.changes[f.id]) Object.assign(f, p.changes[f.id])
  return copy
}

export const TYPE_LABEL: Record<string, string> = {
  TEXT_FIELD: 'Tekst', TEXTAREA: 'Tekst długi', NUMBER: 'Liczba', DATEPICKER: 'Data', SELECT: 'Lista', RADIO: 'Jednokrotny wybór',
  CHECKBOX: 'Wielokrotny wybór', FILE_UPLOADER: 'Załącznik', SECTION: 'Sekcja', REPEATING_SECTION: 'Sekcja powtarzalna',
  TEXT_BLOCK: 'Tekst informacyjny', CONSENT_SECTION: 'Zgody',
}
