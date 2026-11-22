import { expect, test, type Page } from '@playwright/test'

// Brief 14 against live servers with one project in the database (any form whose page 2 has the
// "Osoba odpowiedzialna… jest wnioskodawcą" radio driving "Imię", e.g. results/4-swietlica.coi.json).
// The import test mocks POST /api/v1/forms, so no LLM is called.
const token = process.env.E2E_TOKEN ?? ''
const shot = (page: Page, name: string) => page.screenshot({ path: `e2e/screenshots/${name}.png` })
test.describe.configure({ mode: 'serial', timeout: 90_000 })
test.beforeEach(async ({ page }) => {
  test.skip(!token, 'E2E_TOKEN not set')
  await page.addInitScript((t) => sessionStorage.setItem('coi.token', t), token)
})

async function projectId(page: Page) {
  const r = await page.request.get('/api/v1/forms', { headers: { Authorization: `Bearer ${token}` } })
  const { items } = (await r.json()) as { items: { id: string; title: string }[] }
  return process.env.E2E_PROJECT ?? items.find((i) => /świetlic/i.test(i.title))!.id // E2E_PROJECT keeps fresh imports (e.g. for screenshots) untouched
}
async function openMockup(page: Page, id: string, mode: 'view' | 'edit') {
  await page.goto(`/#/projekt/${id}`) // the editor opens on the first page, in edit mode
  await page.getByTestId(`mode-${mode}`).click()
  return page.getByTestId('preview')
}
const step = (page: Page, i: number) => page.getByTestId('preview').getByRole('list', { name: 'Kroki wniosku' }).getByRole('button').nth(i).click()

test('label edited on the mockup is saved and survives a reload', async ({ page }) => {
  const id = await projectId(page)
  const pv = await openMockup(page, id, 'edit')
  const name = `Imię wnioskodawcy E2E ${Date.now() % 100000}` // a new value each run, so there is always something to save
  await pv.getByTestId('label-input').first().fill(name)
  await shot(page, '14-edit-mode')
  await page.getByTestId('save').click()
  await expect(page.getByText('Zapisano zmiany')).toBeVisible()
  await page.reload()
  await page.getByTestId('mode-view').click()
  await expect(page.getByTestId('preview').getByText(name)).toBeVisible()
  await page.getByTestId('mode-edit').click()
  await expect(page.getByTestId('label-input').first()).toHaveValue(name)
})

test('fields and sections added, moved and removed on the mockup pass server validation', async ({ page }) => {
  const id = await projectId(page)
  const pv = await openMockup(page, id, 'edit')
  const before = await pv.getByTestId('edit-field').count()
  const section = pv.locator('[data-section]').first()
  await section.getByRole('combobox', { name: /Typ nowego pola/ }).selectOption('RADIO')
  await section.getByTestId('add-field').click()
  const added = section.getByTestId('edit-field').last()
  await expect(added.getByTestId('label-input')).toHaveValue('Nowe pole')
  await added.getByTestId('label-input').fill('Czy E2E?')
  await added.getByTestId('option-input').first().fill('Tak')
  await added.getByRole('button', { name: /Przesuń wyżej/ }).click()
  await expect(section.getByTestId('edit-field').first().getByTestId('label-input')).toHaveValue('Czy E2E?')
  await pv.getByTestId('add-section').click()
  await expect(pv.getByTestId('edit-field')).toHaveCount(before + 2)
  await section.getByTestId('edit-field').first().getByTestId('delete-field').click()
  await page.getByRole('button', { name: 'Cofnij' }).click()
  await expect(section.getByTestId('edit-field').first().getByTestId('label-input')).toHaveValue('Czy E2E?')
  await shot(page, '14-structure-edit')
  await page.getByTestId('save').click()
  await expect(page.getByText('Zapisano zmiany')).toBeVisible()
  // clean up for the next run: remove both additions and save again
  await section.getByTestId('edit-field').first().getByTestId('delete-field').click()
  await pv.locator('[data-section]').last().getByRole('button', { name: /^Usuń: Nowa sekcja/ }).click()
  await expect(pv.getByTestId('edit-field')).toHaveCount(before)
  await page.getByTestId('save').click()
  await expect(page.getByText('Zapisano zmiany').first()).toBeVisible()
})

test('graphical condition rewrites the text, saves, and SHOW follows it in the mockup', async ({ page }) => {
  const id = await projectId(page)
  const pv = await openMockup(page, id, 'edit')
  await step(page, 1)
  const imie = pv.getByTestId('edit-field').filter({ has: page.getByTestId('condition-mark') }).first()
  await expect(imie.getByTestId('label-input')).toHaveValue('Imię')
  await imie.getByTestId('edit-condition').click()
  const dlg = page.getByTestId('condition-dialog')
  const row = dlg.getByTestId('cond-row').first()
  // flip the condition to the other option (Nie -> Tak in the generated form; back again on the next run)
  const [from, to] = (await row.getByRole('checkbox', { name: 'Nie' }).isChecked()) ? ['Nie', 'Tak'] : ['Tak', 'Nie']
  await row.getByRole('checkbox', { name: from }).setChecked(false)
  await row.getByRole('checkbox', { name: to }).setChecked(true)
  await dlg.getByRole('tab', { name: 'Tekst' }).click()
  await expect(dlg.getByTestId('cond-text')).toHaveValue(new RegExp(String.raw`^\("${to}" in tabs\['Wniosek o wynajęcie\/użyczenie świetlicy wiejskiej' in title\]\.questions\[.+\.field\.__userAnswer\)$`))
  await dlg.getByRole('tab', { name: 'Graficzny' }).click()
  await shot(page, '14-condition-graphic')
  await dlg.getByTestId('cond-save').click()
  await expect(dlg).toBeHidden()
  await expect(imie.getByTestId('condition-mark')).toContainText(`„${to}”`)
  await page.getByTestId('save').click()
  await expect(page.getByText('Zapisano zmiany')).toBeVisible()

  await page.getByTestId('mode-view').click()
  await step(page, 1)
  const radio = pv.getByRole('group', { name: /Osoba odpowiedzialna/ })
  const field = pv.getByRole('textbox', { name: /^Imię/ })
  await radio.getByLabel(from).check()
  await expect(field).toBeHidden()
  await radio.getByLabel(to).check()
  await expect(field).toBeVisible()
  await shot(page, '14-show-after-edit')
})

test('broken text blocks saving', async ({ page }) => {
  const id = await projectId(page)
  const pv = await openMockup(page, id, 'edit')
  await step(page, 1)
  await pv.getByTestId('edit-condition').first().click()
  const dlg = page.getByTestId('condition-dialog')
  await dlg.getByRole('tab', { name: 'Tekst' }).click()
  const txt = dlg.getByTestId('cond-text')
  const good = await txt.inputValue()
  await txt.fill(good.slice(0, -5))
  await expect(dlg.getByTestId('cond-errors')).toContainText('Błąd składni')
  await expect(dlg.getByTestId('cond-save')).toBeDisabled()
  await txt.fill(good.replace(/'imie'|'[a-z_]+' in field\.techName\]\.field\.__userAnswer/, "'nie_ma_takiego' in field.techName].field.__userAnswer"))
  await expect(dlg.getByTestId('cond-errors')).toContainText('Nie ma takiego pola')
  await expect(dlg.getByTestId('cond-save')).toBeDisabled()
  await txt.fill('$exists(' + good + ')') // valid, but not something the builder can show
  await expect(dlg.getByTestId('cond-save')).toBeEnabled()
  await dlg.getByRole('tab', { name: 'Graficzny' }).click()
  await expect(dlg.getByTestId('not-graphical')).toBeVisible()
  await dlg.getByRole('tab', { name: 'Tekst' }).click()
  await txt.fill(good.slice(0, -5))
  await shot(page, '15-condition-error')
  await dlg.getByRole('button', { name: 'Anuluj' }).click()
  await expect(dlg).toBeHidden()
})

test('one editor: review notes with a suggested action, accept, red dots per page', async ({ page }) => {
  const id = await projectId(page)
  await page.goto(`/#/projekt/${id}`)
  await expect(page.getByTestId('preview')).toHaveAttribute('data-mode', 'edit')
  await expect(page.getByRole('tab', { name: 'Pola i uwagi' })).toHaveCount(0) // no second editor
  const flagged = page.locator('[data-testid=page-link]:not([data-open="0"])')
  if (await flagged.count()) await flagged.last().click()
  const note = page.getByTestId('review-open').first()
  if (await note.count()) {
    await expect(note.getByTestId('notice')).toContainText('Co zrobić:')
    await note.scrollIntoViewIfNeeded()
  }
  await shot(page, '15-editor')
  await page.getByTestId('page-link').first().click()
  await expect(page.getByLabel('Tytuł formularza')).toBeVisible()
  await shot(page, '15-editor-overview')
})

test('save error names the field, explains it and jumps to it', async ({ page }) => {
  const id = await projectId(page)
  await page.goto(`/#/projekt/${id}`)
  await step(page, 1)
  // delete the radio that "Imię" depends on: the server rejects the dangling condition (R6)
  await page.getByTestId('preview').getByRole('button', { name: /^Usuń: Osoba odpowiedzialna/ }).click()
  await page.getByTestId('save').click()
  const box = page.getByTestId('save-errors')
  await expect(box).toBeVisible()
  await expect(box).toContainText('Warunek wskazuje usunięte pole')
  await expect(box).toContainText('Co zrobić:')
  await expect(page.getByTestId('save-error-field').first()).toBeInViewport()
  await shot(page, '15-save-error')
})

test('rejected upload says what to do', async ({ page }) => {
  await page.goto('/#/')
  await page.getByTestId('open-import').click()
  await page.getByTestId('import-input').setInputFiles({ name: 'notatki.txt', mimeType: 'text/plain', buffer: Buffer.from('x') })
  const row = page.getByTestId('queue-row')
  await expect(row).toHaveAttribute('data-status', 'rejected')
  await expect(row).toContainText('Wczytaj plik')
  await shot(page, '15-import-rejected')
})

test('import keeps running with the dialog closed; the menu shows its state and reopens the same queue', async ({ page }) => {
  const id = await projectId(page)
  let release!: () => void
  const held = new Promise<void>((r) => { release = r })
  await page.route('**/api/v1/forms?report=true', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    await held
    const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
    await route.fulfill({
      status: 200, headers: { 'Content-Type': 'text/event-stream' },
      body: sse('stage', { stage: 'parse', status: 'done', seconds: 1.2 }) + sse('result', { id, form: {}, report: { needs_review: [], cost: 0.01, seconds: 3 } }),
    })
  })
  await page.goto('/#/')
  const menu = page.getByTestId('open-import')
  await menu.click()
  await page.getByTestId('import-input').setInputFiles({ name: 'wniosek-e2e.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 e2e') })
  await expect(page.getByTestId('queue-row')).toHaveAttribute('data-status', 'running')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toBeHidden()
  await expect(menu).toHaveAttribute('data-state', 'running')
  await expect(menu).toContainText('Import: 1 w toku')
  expect(await page.evaluate(() => !window.dispatchEvent(new Event('beforeunload', { cancelable: true })))).toBe(true)
  await shot(page, '14-import-running-closed')
  await menu.click()
  await expect(page.getByTestId('queue-row')).toHaveAttribute('data-status', 'running')
  await page.keyboard.press('Escape')
  release()
  await expect(menu).toHaveAttribute('data-state', 'done')
  await expect(menu).toContainText('Import: 1 gotowy')
  expect(await page.evaluate(() => !window.dispatchEvent(new Event('beforeunload', { cancelable: true })))).toBe(false)
  await menu.click()
  await expect(page.getByTestId('queue-row')).toHaveAttribute('data-status', 'done')
  await shot(page, '14-import-reopened-done')
})
