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

// ---- structure edits (mockup edit mode). Layout follows the generator: sections stacked at x=0, section rows = children's
// bottom + 1, questionOrder = y for sections and the index for children.
export const INPUT = ['TEXT_FIELD', 'TEXTAREA', 'NUMBER', 'DATEPICKER', 'RADIO', 'CHECKBOX', 'SELECT', 'FILE_UPLOADER']
export const CHOICE = ['RADIO', 'CHECKBOX', 'SELECT']
const byPos = (qs: Q[]) => qs.slice().sort((a, b) => a.y - b.y || a.x - b.x)
const bottom = (qs: Q[]) => Math.max(0, ...qs.map((q) => q.y + q.rows))
const gridWidth = (qs: Q[]) => Math.max(3, ...qs.map((q) => q.x + q.cols))

export type Spot = { tab: Tab; list: Q[]; q: Q; parent?: Q }
export function locate(form: Form, id: string): Spot | null {
  for (const tab of tabsOf(form)) for (const q of tab.questions) {
    if (q.field.id === id) return { tab, list: tab.questions, q }
    const c = (q.field.repeatingSectionGrid ?? []).find((c) => c.field.id === id)
    if (c) return { tab, list: q.field.repeatingSectionGrid!, q: c, parent: q }
  }
  return null
}
function relayout(tab: Tab) {
  let y = 0
  for (const q of byPos(tab.questions)) {
    const kids = q.field.repeatingSectionGrid
    if (kids && (q.field.type === 'SECTION' || q.field.type === 'REPEATING_SECTION')) {
      byPos(kids).forEach((c, i) => { (c.field as { questionOrder?: number }).questionOrder = i })
      q.rows = bottom(kids) + 1
    }
    q.y = y
    ;(q.field as { questionOrder?: number }).questionOrder = y
    y += q.rows
  }
}
const slug = (s: string) => s.normalize('NFKD').replace(/ł/g, 'l').replace(/Ł/g, 'L').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 60) || 'pole'
export const option = (name: string) => ({ id: crypto.randomUUID(), name, techName: slug(name) })

export function newField(form: Form, type: string): Field {
  const used = new Set(fieldsOf(form).map((f) => f.techName))
  const base = slug(`nowe ${TYPE_LABEL[type] ?? 'pole'}`)
  let techName = base
  for (let i = 2; used.has(techName); i++) techName = `${base}_${i}`
  const section = type === 'SECTION' || type === 'REPEATING_SECTION'
  return {
    id: crypto.randomUUID(), type, techName, title: section ? 'Nowa sekcja' : type === 'TEXT_BLOCK' ? '' : 'Nowe pole',
    description: section ? '<html><head></head><body></body></html>' : type === 'TEXT_BLOCK' ? 'Treść informacji' : '',
    options: CHOICE.includes(type) ? [option('Opcja 1'), option('Opcja 2')] : [], validation: INPUT.includes(type) ? ['REQUIRED'] : [],
    readOnly: false, repeatingSectionGrid: [], states: [], questionOrder: 0, tooltipMessage: '',
  } as Field
}
export function addField(form: Form, sectionId: string, type: string): string {
  const s = locate(form, sectionId)!
  const kids = (s.q.field.repeatingSectionGrid ??= [])
  const field = newField(form, type)
  kids.push({ x: 0, y: bottom(kids), rows: 1, cols: gridWidth(kids), field })
  relayout(s.tab)
  return field.id
}
export function addSection(form: Form, tabId: string, type = 'SECTION'): string {
  const tab = tabsOf(form).find((t) => t.id === tabId)!
  const field = newField(form, type)
  tab.questions.push({ x: 0, y: bottom(tab.questions), rows: 1, cols: gridWidth(tab.questions), field })
  // an empty section is not rendered at all, so it starts with one field
  addField(form, field.id, tab.type === 'FINISH' ? 'TEXT_BLOCK' : 'TEXT_FIELD')
  return field.id
}
export function removeField(form: Form, id: string) {
  const s = locate(form, id)
  if (!s) return
  s.list.splice(s.list.indexOf(s.q), 1)
  // close the gap when nothing else sits in the removed rows
  if (s.parent && !s.list.some((c) => c.y < s.q.y + s.q.rows && c.y + c.rows > s.q.y)) for (const c of s.list) if (c.y > s.q.y) c.y -= s.q.rows
  relayout(s.tab)
}
// Swap places with the previous/next sibling in reading order (the two keep each other's grid slot).
export function moveField(form: Form, id: string, dir: -1 | 1) {
  const s = locate(form, id)
  if (!s) return
  const sorted = byPos(s.list)
  const other = sorted[sorted.indexOf(s.q) + dir]
  if (!other) return
  if (!s.parent) s.q.y = other.y + dir * 0.5 // sections differ in height: relayout restacks them in the new order
  else for (const k of ['x', 'y', 'cols'] as const) [s.q[k], other[k]] = [other[k], s.q[k]]
  relayout(s.tab)
}
export const canMove = (form: Form, id: string, dir: -1 | 1) => {
  const s = locate(form, id)
  if (!s) return false
  const sorted = byPos(s.list)
  return !!sorted[sorted.indexOf(s.q) + dir]
}
// How many conditions name this field (by techName, the way JSONata addresses it).
export const usedBy = (form: Form, f: Field) =>
  f.techName ? fieldsOf(form).filter((x) => x.id !== f.id && x.states?.some((s) => s.query.includes(`'${f.techName}' in field`))).length : 0
