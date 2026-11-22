import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'

// Full clerk flow against live servers: import (real LLM run), log, list "nowe", editor review marks, resolve one point,
// citizen mockup with SHOW, pasted-JSON preview, delete with confirmation. Screenshots land in e2e/screenshots/.
const MAT = path.resolve(import.meta.dirname, '../../../materials')
const pick = (prefix: string, ext: string) => {
  const dir = readdirSync(MAT).find((d) => d.startsWith(prefix))!
  return path.join(MAT, dir, readdirSync(path.join(MAT, dir)).find((f) => f.endsWith(ext))!)
}
const GOOD = [pick('3. ', '.docx'), pick('4. ', '.docx')]
const BAD = pick('7. ', '.JPE') // extension outside /api/v1/info limits: rejected before upload
const REFERENCE = pick('1. ', '.json')
const shot = (page: Page, name: string) => page.screenshot({ path: `e2e/screenshots/${name}.png`, fullPage: false })

test.describe.configure({ mode: 'serial' })
test.beforeEach(async ({ page }) => {
  const token = process.env.E2E_TOKEN
  test.skip(!token, 'E2E_TOKEN not set')
  await page.addInitScript((t) => sessionStorage.setItem('coi.token', t), token!)
})

// Click radio options one by one on every step until the number of rendered fields changes: SHOW works.
async function showChangesSomething(page: Page) {
  const pv = page.getByTestId('preview')
  const count = () => pv.locator('[data-field]').count()
  const steps = await pv.getByRole('list', { name: 'Kroki wniosku' }).getByRole('button').count()
  for (let s = 0; s < steps; s++) {
    await pv.getByRole('list', { name: 'Kroki wniosku' }).getByRole('button').nth(s).click({ timeout: 3000 }).catch(() => {})
    const radios = pv.locator('input[type=radio]:not([disabled])')
    for (let i = 0; i < Math.min(await radios.count(), 20); i++) {
      const before = await count()
      await radios.nth(i).click({ timeout: 1000 }).catch(() => {})
      await page.waitForTimeout(150)
      if ((await count()) !== before) return true
    }
  }
  return false
}

test('clerk flow', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Projekty' })).toBeVisible()
  const before = await page.getByTestId('project-row').count()

  // import: 2 good files + 1 bad
  await page.getByTestId('open-import').click()
  await page.getByTestId('import-input').setInputFiles([...GOOD, BAD])
  const rows = page.getByTestId('queue-row')
  await expect(rows).toHaveCount(3)
  await expect(rows.nth(2)).toHaveAttribute('data-status', 'rejected')
  await expect(rows.nth(2)).toContainText('Nieobsługiwany typ pliku .jpe')
  await rows.nth(0).getByRole('button', { name: /Pokaż przebieg/ }).click()
  await expect(rows.nth(0).getByTestId('queue-log')).toContainText('Odczyt dokumentu', { timeout: 60_000 })
  await shot(page, '01-import-running')
  await expect(page.locator('[data-testid=queue-row][data-status=done]')).toHaveCount(2, { timeout: 12 * 60_000 })
  await expect(rows.nth(0).getByTestId('queue-log')).toContainText('Projekt zapisany')
  await shot(page, '02-import-done-log')
  await page.getByRole('button', { name: 'Zamknij', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeHidden()

  // list with "nowe"
  await expect(page.getByTestId('project-row')).toHaveCount(before + 2)
  await expect(page.getByTestId('fresh-badge')).toHaveCount(2)
  await shot(page, '03-list-new')

  // editor: open the new project with the most review points
  const fresh = page.getByTestId('project-row').filter({ has: page.getByTestId('fresh-badge') })
  await fresh.first().getByRole('button').first().click()
  await expect(page.getByTestId('open-count').or(page.getByText('Wszystkie uwagi rozstrzygnięte'))).toBeVisible()
  const flagged = page.locator('[data-testid=page-link]:not([data-open="0"])')
  test.skip((await flagged.count()) === 0, 'imported form has no review points')
  const pageLink = flagged.last()
  const name = (await pageLink.locator('span').first().textContent())!
  const openBefore = Number(await pageLink.getAttribute('data-open'))
  await pageLink.click()
  await expect(page.locator('[data-review=open]').first()).toBeVisible()
  await shot(page, '04-editor-red-marks')

  // resolve one point and save; the count (and the dot when it was the last one) stays gone after a reload
  await page.getByTestId('accept-point').first().click()
  await page.getByTestId('save').click()
  await expect(page.getByText('Zapisano zmiany')).toBeVisible()
  await page.reload()
  const after = page.getByTestId('page-link').filter({ hasText: name })
  await expect(after).toHaveAttribute('data-open', String(openBefore - 1))
  if (openBefore === 1) await expect(after.getByTestId('red-dot')).toHaveCount(0)
  await after.click()
  await shot(page, '05-editor-resolved')
  await page.setViewportSize({ width: 820, height: 1180 }) // tablet
  await shot(page, '05b-editor-tablet')
  await page.setViewportSize({ width: 1366, height: 900 })

  // citizen mockup of the edited form
  await page.getByRole('tab', { name: 'Makieta dla obywatela' }).click()
  await expect(page.getByTestId('preview')).toBeVisible()
  const projectShow = await showChangesSomething(page)
  await shot(page, '06-mockup-show')
  await page.getByRole('button', { name: 'Projekty' }).first().click()

  // pasted JSON preview (reference form #1) with working SHOW
  await page.getByRole('button', { name: 'Podgląd JSON' }).click()
  await page.getByLabel('Treść JSON').fill(readFileSync(REFERENCE, 'utf8'))
  await page.getByRole('button', { name: 'Pokaż makietę' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  await expect(page.getByTestId('preview')).toBeVisible()
  expect(projectShow || (await showChangesSomething(page)), 'SHOW changed the visible fields in a mockup').toBe(true)
  await shot(page, '07-json-preview-show')
  await page.getByRole('button', { name: 'Projekty' }).first().click()

  // delete one of the imported projects, with confirmation
  const count = await page.getByTestId('project-row').count()
  await fresh.first().getByRole('button', { name: /Usuń projekt/ }).click()
  await expect(page.getByRole('alertdialog')).toContainText('Tego nie da się cofnąć')
  await shot(page, '08-delete-confirm')
  await page.getByRole('button', { name: 'Usuń projekt' }).click()
  await expect(page.getByTestId('project-row')).toHaveCount(count - 1)
  await shot(page, '09-after-delete')
})
