import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'
import { check, emit, parse } from '../src/lib/condition'

// No browser: every SHOW query in app/results/ parses into the graphical model and emits back the same text,
// and passes the reference check against its own form.
const DIR = path.resolve(import.meta.dirname, '../../results')
const forms = readdirSync(DIR).filter((f) => f.endsWith('.coi.json')).map((f) => [f, JSON.parse(readFileSync(path.join(DIR, f), 'utf8'))] as const)
const squash = (s: string) => s.replace(/\s+/g, '')

test('generator queries round-trip through the graphical model', () => {
  let n = 0, graphical = 0
  for (const [name, form] of forms) {
    const seen = new Set<string>()
    const visit = (o: unknown) => {
      if (Array.isArray(o)) return o.forEach(visit)
      if (!o || typeof o !== 'object') return
      for (const s of (o as { states?: { query: string }[] }).states ?? []) seen.add(s.query)
      Object.values(o).forEach(visit)
    }
    visit(form)
    for (const q of seen) {
      n++
      expect(check(q, form), `${name}: ${q}`).toEqual([])
      const m = parse(q)
      if (m) graphical++
      if (m) expect(squash(emit(m)), `${name}: ${q}`).toBe(squash(q))
    }
  }
  console.log(`${graphical} of ${n} queries are graphical`)
  expect(graphical).toBeGreaterThan(n * 0.8)
})

test('model edits emit generator-shaped text', () => {
  const ref = { page: 'Dane', section: 'adres', tech: 'kraj', repeating: false }
  const p = "tabs['Dane' in title].questions['adres' in field.techName].field.repeatingSectionGrid['kraj' in field.techName].field.__userAnswer"
  expect(emit({ negate: false, join: 'and', rows: [{ ...ref, op: 'notin', values: ['Polska'] }] })).toBe(`$not("Polska" in ${p})`)
  expect(emit({ negate: false, join: 'or', rows: [{ ...ref, op: 'in', values: ['A', 'B'] }] })).toBe(`("A" in ${p}) or ("B" in ${p})`)
  const two = emit({ negate: true, join: 'and', rows: [{ ...ref, op: 'in', values: ['A', 'B'] }, { ...ref, op: 'in', values: ['C'] }] })
  expect(two).toBe(`$not((("A" in ${p}) or ("B" in ${p})) and ("C" in ${p}))`)
  expect(parse(two)).toEqual({ negate: true, join: 'and', rows: [{ ...ref, op: 'in', values: ['A', 'B'] }, { ...ref, op: 'in', values: ['C'] }] })
  expect(parse(`$count(${p}) > 1`)).toBeNull()
  expect(check(`("A" in ${p}`, { tabs: [] } as never)[0].message).toMatch(/składni/)
})
