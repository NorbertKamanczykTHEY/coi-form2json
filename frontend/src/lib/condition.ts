import jsonata from 'jsonata'
import type { Form } from './api'
import { tabsOf, type Field } from './form'

// JSONata of `states` (SHOW / READ_ONLY) in the generator's shape (docs/design/generator.md §4):
// leaf ("Opcja" in tabs['Strona' in title].questions['sekcja' in field.techName].field.repeatingSectionGrid['pole' in field.techName].field.__userAnswer),
// in a repeating section …field.__userAnswer[$repeatingSectionIndex]['pole' in fieldTechName].answers; $not(…); (A) and (B).

export type Ref = { page: string; section: string; tech: string; repeating: boolean }
export type Row = Ref & { op: 'in' | 'notin'; values: string[] }
// The graphical model: rows joined by one operator, optionally negated as a whole.
export type Model = { negate: boolean; join: 'and' | 'or'; rows: Row[] }

// A choice field that can drive a condition, addressed the way JSONata addresses it.
export type Controller = Ref & { key: string; label: string; options: string[]; owner: string }
export const refKey = (r: Ref) => `${r.page}\u0000${r.section}\u0000${r.tech}`

export function controllers(form: Form): Controller[] {
  const out: Controller[] = []
  for (const t of tabsOf(form)) for (const q of t.questions) {
    const s = q.field
    for (const c of s.repeatingSectionGrid ?? []) {
      const f = c.field
      if (!['RADIO', 'CHECKBOX', 'SELECT'].includes(f.type) || !f.options?.length || !f.techName || !s.techName) continue
      const ref = { page: t.title, section: s.techName, tech: f.techName, repeating: s.type === 'REPEATING_SECTION' }
      out.push({ ...ref, key: refKey(ref), label: f.title || f.techName, options: f.options.map((o) => o.name), owner: s.id })
    }
  }
  return out
}

// ---- emit ----------------------------------------------------------------
const jstr = (s: string) => JSON.stringify(s)
export function path(r: Ref) {
  const base = `tabs['${r.page.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}' in title].questions['${r.section}' in field.techName].field`
  return r.repeating
    ? `${base}.__userAnswer[$repeatingSectionIndex]['${r.tech}' in fieldTechName].answers`
    : `${base}.repeatingSectionGrid['${r.tech}' in field.techName].field.__userAnswer`
}
function rowText(r: Row, top: boolean) {
  const leaves = r.values.map((v) => `(${jstr(v)} in ${path(r)})`)
  const inner = leaves.join(' or ')
  if (r.op === 'notin') return `$not(${leaves.length === 1 ? inner.slice(1, -1) : inner})`
  return top || leaves.length === 1 ? inner : `(${inner})`
}
export function emit(m: Model): string {
  const rows = m.rows.filter((r) => r.values.length)
  if (!rows.length) return ''
  const body = rows.length === 1 ? rowText(rows[0], !m.negate) : rows.map((r) => rowText(r, false)).join(` ${m.join} `)
  if (!m.negate) return body
  return `$not(${rows.length === 1 && rows[0].op === 'in' && rows[0].values.length === 1 ? body.slice(1, -1) : body})`
}

// ---- parse ---------------------------------------------------------------
type Node = { leaf: Ref & { value: string } } | { not: Node } | { and: Node[] } | { or: Node[] }
const VAL = String.raw`"((?:[^"\\]|\\.)*)"\s+in\s+`
const PATH = String.raw`tabs\['((?:[^'\\]|\\.)*)'\s+in\s+title\]\.questions\['([^']+)'\s+in\s+field\.techName\]\.field` +
  String.raw`(?:\.repeatingSectionGrid\['([^']+)'\s+in\s+field\.techName\]\.field\.__userAnswer|\.__userAnswer\[\$repeatingSectionIndex\]\['([^']+)'\s+in\s+fieldTechName\]\.answers)`
const LEAF = new RegExp(VAL + PATH, 'y')

function tree(src: string): Node | null {
  let i = 0
  const ws = () => { while (/\s/.test(src[i] ?? '')) i++ }
  const eat = (s: string) => { ws(); if (src.startsWith(s, i)) { i += s.length; return true } return false }
  const word = (w: string) => { ws(); if (src.startsWith(w, i) && !/\w/.test(src[i + w.length] ?? '')) { i += w.length; return true } return false }
  function chain(op: 'and' | 'or', next: () => Node | null): Node | null {
    const first = next()
    if (!first) return null
    const parts = [first]
    while (word(op)) { const n = next(); if (!n) return null; parts.push(n) }
    return parts.length === 1 ? first : ({ [op]: parts } as Node)
  }
  const or = (): Node | null => chain('or', and)
  const and = (): Node | null => chain('and', unary)
  function unary(): Node | null {
    if (eat('$not(')) { const n = or(); return n && eat(')') ? { not: n } : null }
    if (eat('(')) { const n = or(); return n && eat(')') ? n : null }
    ws()
    LEAF.lastIndex = i
    const m = LEAF.exec(src)
    if (!m) return null
    i = LEAF.lastIndex
    return { leaf: { value: JSON.parse(`"${m[1]}"`), page: m[2].replace(/\\(.)/g, '$1'), section: m[3], tech: m[4] ?? m[5], repeating: !m[4] } }
  }
  const n = or()
  ws()
  return n && i === src.length ? n : null
}

// "field is one of" = one leaf, or leaves on the same field joined with or.
function asRow(n: Node): Row | null {
  if ('leaf' in n) { const { value, ...ref } = n.leaf; return { ...ref, op: 'in', values: [value] } }
  if ('or' in n && n.or.every((c) => 'leaf' in c)) {
    const ls = n.or.map((c) => (c as { leaf: Ref & { value: string } }).leaf)
    if (ls.every((l) => refKey(l) === refKey(ls[0]))) { const { value: _, ...ref } = ls[0]; return { ...ref, op: 'in', values: ls.map((l) => l.value) } }
  }
  if ('not' in n) { const r = asRow(n.not); if (r && r.op === 'in') return { ...r, op: 'notin' } }
  return null
}
function asFlat(n: Node): Model | null {
  const r = asRow(n)
  if (r) return { negate: false, join: 'and', rows: [r] }
  for (const join of ['and', 'or'] as const) {
    if (join in n) {
      const rows = (n as Record<string, Node[]>)[join].map(asRow)
      if (rows.every(Boolean)) return { negate: false, join, rows: rows as Row[] }
    }
  }
  return null
}
// null when the text cannot be shown graphically (other functions, nested and/or mixes, comparisons…)
export function parse(query: string): Model | null {
  const n = tree(query.trim())
  if (!n) return null
  const flat = asFlat(n)
  if (flat) return flat
  if ('not' in n) { const inner = asFlat(n.not); if (inner) return { ...inner, negate: true } }
  return null
}

// ---- check ---------------------------------------------------------------
export type Problem = { message: string; position?: number }
const REF = new RegExp(`(?:${VAL})?${PATH}`, 'g')

// Syntax via the jsonata library, then every reference must resolve to a field of this form (same rule R6 the server applies).
export function check(query: string, form: Form, owner?: Field): Problem[] {
  if (!query.trim()) return [{ message: 'Wyrażenie jest puste.' }]
  try { jsonata(query) } catch (e) {
    const err = e as { message?: string; position?: number }
    return [{ message: `Błąd składni: ${err.message ?? e}`, position: err.position }]
  }
  const fields = new Map<string, { f: Field; section: Field }>()
  for (const t of tabsOf(form)) for (const q of t.questions) for (const c of q.field.repeatingSectionGrid ?? [])
    fields.set(refKey({ page: t.title, section: q.field.techName ?? '', tech: c.field.techName ?? '', repeating: false }), { f: c.field, section: q.field })
  const out: Problem[] = []
  for (const m of query.matchAll(REF)) {
    const ref = { page: m[2].replace(/\\(.)/g, '$1'), section: m[3], tech: m[4] ?? m[5], repeating: !m[4] }
    const hit = fields.get(refKey(ref))
    const where = `strona „${ref.page}”, sekcja ${ref.section}, pole ${ref.tech}`
    if (!hit) { out.push({ message: `Nie ma takiego pola: ${where}.`, position: m.index }); continue }
    if (ref.repeating !== (hit.section.type === 'REPEATING_SECTION'))
      out.push({ message: `Pole ${ref.tech} ${ref.repeating ? 'nie leży' : 'leży'} w sekcji powtarzalnej: użyj ${ref.repeating ? 'ścieżki repeatingSectionGrid' : 'ścieżki [$repeatingSectionIndex]'}.`, position: m.index })
    else if (ref.repeating && owner && !(hit.section.repeatingSectionGrid ?? []).some((c) => c.field.id === owner.id))
      out.push({ message: `Pole spoza sekcji powtarzalnej ${ref.section} nie może zależeć od pola w jej środku.`, position: m.index })
    if (m[1] !== undefined && hit.f.options?.length) {
      const v = JSON.parse(`"${m[1]}"`)
      if (!hit.f.options.some((o) => o.name === v)) out.push({ message: `„${v}” nie jest opcją pola ${hit.f.title || ref.tech}.`, position: m.index })
    }
  }
  if (!out.length && !query.includes('__userAnswer')) out.push({ message: 'Wyrażenie nie odwołuje się do żadnego pola formularza.' })
  return out
}

// ---- describe ------------------------------------------------------------
const quote = (vs: string[]) => vs.map((v) => `„${v}”`).join(' lub ')
export function describe(query: string, form: Form): string {
  const m = parse(query)
  if (!m) return 'warunek złożony (do edycji jako tekst)'
  const label = new Map(controllers(form).map((c) => [c.key, c.label]))
  const parts = m.rows.map((r) => `${label.get(refKey(r)) ?? r.tech} ${r.op === 'in' ? (r.values.length > 1 ? 'to jedno z:' : 'to') : r.values.length > 1 ? 'to żadne z:' : 'to nie'} ${quote(r.values)}`)
  const s = parts.join(m.join === 'and' ? ' i ' : ' lub ')
  return m.negate ? `nie zachodzi: ${s}` : s
}
