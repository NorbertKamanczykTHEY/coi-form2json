import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

// No browser: every needs_review reason in app/results/*.report.json maps to a specific message (not the fallback),
// and every message has a title, a reason and an action.
Object.assign(globalThis, { window: globalThis, sessionStorage: { getItem: () => null } }) // lib/api reads these at load
const DIR = path.resolve(import.meta.dirname, '../../results')

test('review reasons from real reports map to specific messages', async () => {
  const { reviewMsg, validationMsg, apiMsg, conditionMsg } = await import('../src/lib/messages')
  const { ApiError } = await import('../src/lib/api')
  const whys = readdirSync(DIR).filter((f) => f.endsWith('.report.json'))
    .flatMap((f) => (JSON.parse(readFileSync(path.join(DIR, f), 'utf8')).needs_review ?? []).map((n: { why?: string }) => n.why ?? ''))
  expect(whys.length).toBeGreaterThan(0)
  const unmapped = whys.filter((w) => reviewMsg(w).title === 'Do sprawdzenia')
  expect(unmapped).toEqual([])
  const fallback = reviewMsg('coś zupełnie nowego')
  expect(fallback.why).toBe('coś zupełnie nowego')
  for (const m of [...whys.map(reviewMsg), validationMsg({ rule: 'R6', message: "'imie' refers to missing x" }), conditionMsg('Wyrażenie jest puste.'),
    ...[400, 401, 413, 415, 422, 504].map((s) => apiMsg(new ApiError(s, 'x')))]) {
    expect(m.title && m.why && m.action).toBeTruthy()
  }
  expect(apiMsg(new ApiError(400, 'Invalid file name', [], 'invalid_filename')).action).toMatch(/Skróć nazwę pliku do/)
})
