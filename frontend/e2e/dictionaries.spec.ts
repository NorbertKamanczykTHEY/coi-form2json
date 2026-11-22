import { expect, test } from '@playwright/test'

// Dictionary editor against live servers, no LLM: create, add/edit/delete an item, delete the dictionary; TERYT is paged and protected.
test.beforeEach(async ({ page }) => {
  const token = process.env.E2E_TOKEN
  test.skip(!token, 'E2E_TOKEN not set')
  await page.addInitScript((t) => sessionStorage.setItem('coi.token', t), token!)
})

test('dictionary CRUD from the Słowniki view', async ({ page }) => {
  const id = `E2E${Date.now()}`
  await page.goto('/')
  await page.getByRole('button', { name: 'Słowniki' }).click()
  await expect(page.getByTestId('dictionary-row').first()).toBeVisible()
  await expect(page.getByTestId('dictionary-row').filter({ hasText: 'z materiałów' }).first()).toBeVisible()

  await page.getByRole('button', { name: 'Nowy słownik' }).click()
  await page.getByLabel('Nazwa', { exact: true }).fill('Rodzaj zabudowy E2E')
  await page.getByLabel('Nazwa techniczna').fill(id)
  await page.getByLabel('Pozycje, po jednej w wierszu').fill('jednorodzinna\n\nwielorodzinna\n')
  await page.getByRole('button', { name: 'Utwórz słownik' }).click()

  await expect(page.getByRole('heading', { name: 'Rodzaj zabudowy E2E' })).toBeVisible()
  await expect(page.getByTestId('item-row')).toHaveCount(2)
  await page.getByLabel('Nowa pozycja').fill('zagrodowa')
  await page.getByRole('button', { name: 'Dodaj' }).click()
  await expect(page.getByTestId('item-row')).toHaveCount(3)

  await page.getByRole('button', { name: 'Edytuj zagrodowa' }).click()
  await page.getByLabel('Nazwa pozycji').fill('zagrodowa (wiejska)')
  await page.getByRole('button', { name: 'Zapisz pozycję' }).click()
  await expect(page.getByTestId('item-row').filter({ hasText: 'zagrodowa (wiejska)' })).toBeVisible()

  await page.getByRole('button', { name: 'Usuń jednorodzinna' }).click()
  await expect(page.getByTestId('item-row')).toHaveCount(2)

  await page.getByRole('button', { name: 'Zmień nazwę słownika' }).click()
  await page.getByLabel('Nazwa słownika').fill('Zabudowa E2E')
  await page.getByRole('button', { name: 'Zapisz', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Zabudowa E2E' })).toBeVisible()

  await page.getByRole('button', { name: 'Usuń słownik' }).click()
  await expect(page.getByRole('alertdialog')).toContainText('Zabudowa E2E')
  await page.getByRole('alertdialog').getByRole('button', { name: 'Usuń słownik' }).click()
  await expect(page.getByRole('heading', { name: 'Słowniki' })).toBeVisible()
  await expect(page.getByTestId('dictionary-row').filter({ hasText: id })).toHaveCount(0)

  // a big protected dictionary: one page at a time, search with ancestor path, delete disabled
  await page.getByTestId('dictionary-row').filter({ hasText: 'TERYT' }).first().click()
  await expect(page.getByRole('button', { name: 'Usuń słownik' })).toBeDisabled()
  await page.getByLabel('Szukaj pozycji').fill('Nowa Wieś')
  await expect(page.getByTestId('item-row')).toHaveCount(50)
  await expect(page.getByText(/^1–50 z /)).toBeVisible()
  await page.screenshot({ path: 'e2e/screenshots/16-dictionaries.png' })
})
