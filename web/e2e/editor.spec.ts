import { readFile } from 'node:fs/promises'
import { expect, test, type Page } from '@playwright/test'

/** Søknadseditor (FRONTEND §5.5, F3): autosave, revision chat, versions with diff, copy and .docx. */

const isMobile = (name: string) => name === 'mobile'
const textArea = (page: Page) => page.getByRole('textbox', { name: 'Søknadstekst' })
const saveStatus = (page: Page) => page.getByTestId('save-status')
const versionMenu = (page: Page) => page.getByTestId('editor-toolbar').getByRole('button', { name: /^Versjon/ })

/** Opens the newest draft in /soknader (an application in Utkast with three versions). */
async function openFirstDraft(page: Page) {
  await page.goto('/soknader')
  await page.getByTestId('draft-list').getByRole('link').first().click()
  await expect(page).toHaveURL(/\/soknader\/\d+$/)
  await expect(textArea(page)).toHaveValue(/Hei,/)
}

test('autosave 2 s after the last keystroke adds a user version', async ({ page }, info) => {
  await openFirstDraft(page)
  await expect(saveStatus(page)).toHaveText('Lagret')
  await textArea(page).press('End')
  await textArea(page).pressSequentially(' PS: Jeg kan starte i juni.')
  await expect(saveStatus(page)).toHaveText('Ikke lagret')
  await expect(saveStatus(page)).toHaveText('Lagret', { timeout: 6000 })

  if (isMobile(info.project.name)) {
    await page.getByRole('tab', { name: 'Versjoner' }).click()
    await expect(page.getByTestId('version-list').locator('li').first()).toContainText('Versjon 4 · Deg')
  } else {
    await expect(versionMenu(page)).toHaveText('Versjon 4')
    // The chat logs the user's edit.
    await expect(page.getByTestId('revision-chat')).toContainText('Du redigerte · versjon 4')
  }
})

test('revision chat: instruction → background task → new agent version', async ({ page }, info) => {
  await openFirstDraft(page)
  const words = Number((await page.getByTestId('word-count').textContent())!.split(' ')[0])
  if (isMobile(info.project.name)) await page.getByRole('tab', { name: 'Chat' }).click()

  const chat = page.getByTestId('revision-chat')
  await chat.getByRole('textbox', { name: 'Instruksjon til agenten' }).fill('Gjør andre avsnitt kortere')
  await chat.getByRole('button', { name: 'Send' }).click()
  await expect(chat.getByText('Gjør andre avsnitt kortere', { exact: true })).toBeVisible()
  await expect(chat.getByRole('status')).toBeVisible() // agent is writing
  await expect(chat.getByText(/Kuttet siste setning/)).toBeVisible({ timeout: 8000 })
  await expect(chat.getByRole('button', { name: 'Versjon 4' })).toBeVisible()

  if (isMobile(info.project.name)) await page.getByRole('tab', { name: 'Utkast' }).click()
  await expect(textArea(page)).toBeEditable()
  await expect
    .poll(async () => Number((await page.getByTestId('word-count').textContent())!.split(' ')[0]))
    .toBeLessThan(words)
})

test('revision chat: a question is answered without a new version', async ({ page }, info) => {
  await openFirstDraft(page)
  if (isMobile(info.project.name)) await page.getByRole('tab', { name: 'Chat' }).click()
  const chat = page.getByTestId('revision-chat')
  await chat.getByRole('textbox', { name: 'Instruksjon til agenten' }).fill('Hvorfor skriver du at jeg ledet backend?')
  await chat.getByRole('textbox', { name: 'Instruksjon til agenten' }).press('Enter')
  await expect(chat.getByText('Hvorfor skriver du at jeg ledet backend?', { exact: true })).toHaveCount(1)
  await expect(chat.getByText(/^Mock-svar:/)).toBeVisible({ timeout: 8000 })
  await expect(chat.getByRole('button', { name: 'Versjon 4' })).toHaveCount(0)
  if (isMobile(info.project.name)) await page.getByRole('tab', { name: 'Utkast' }).click()
  await expect(textArea(page)).toBeEditable()
  await expect(textArea(page)).not.toHaveValue(/Hvorfor skriver du/)
})

test('versions: diff against the previous version and restore', async ({ page }, info) => {
  await openFirstDraft(page)
  if (isMobile(info.project.name)) {
    await page.getByRole('tab', { name: 'Versjoner' }).click()
    await page.getByTestId('version-list').getByRole('button', { name: /Versjon 3/ }).click()
  } else {
    await versionMenu(page).click()
    await page.getByRole('menuitem', { name: /Versjon 3/ }).click()
  }
  await expect(page).toHaveURL(/versjon=\d+/)
  const view = page.getByTestId('version-view')
  await expect(view.getByTestId('diff-stats')).toContainText('Mot versjon 2')
  await expect(view.locator('[data-diff="removed"]').first()).toBeVisible()

  // Open version 1 and restore it.
  await view.getByRole('button', { name: 'Lukk versjonen' }).click()
  await expect(view).toBeHidden()
  if (isMobile(info.project.name)) {
    await page.getByTestId('version-list').getByRole('button', { name: /Versjon 1/ }).click()
  } else {
    await versionMenu(page).click()
    await page.getByRole('menuitem', { name: /Versjon 1/ }).click()
  }
  await view.getByRole('button', { name: 'Gjenopprett' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Gjenopprettet versjon 1' })).toBeVisible()
  await expect(saveStatus(page)).toHaveText('Lagret')
  if (isMobile(info.project.name)) await page.getByRole('tab', { name: 'Utkast' }).click()
  await expect(textArea(page)).toHaveValue(/Det dere skriver om kodegjennomgang/) // dropped in version 3
})

test('claims can be ticked off; copy and .docx download', async ({ page, context }, info) => {
  test.skip(isMobile(info.project.name), 'clipboard permissions are per browser; one viewport is enough')
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await openFirstDraft(page)
  const claims = page.getByTestId('claims')
  await expect(claims).toContainText('Sjekk 1 påstand')
  await claims.getByRole('checkbox').check()
  await expect(claims).toContainText('Alle påstander er sjekket')

  await page.getByRole('button', { name: 'Kopier' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Kopiert som ren tekst' })).toBeVisible()
  expect(await page.evaluate<string>('navigator.clipboard.readText()')).toMatch(/^Hei,/)

  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: '.docx' }).click()])
  expect(download.suggestedFilename()).toMatch(/^Søknad .+ v3\.docx$/)
  const bytes = await readFile((await download.path())!)
  expect(bytes.subarray(0, 4)).toEqual(Buffer.from([0x50, 0x4b, 0x03, 0x04])) // zip
  expect(bytes.toString('latin1')).toContain('word/document.xml')
})

test('Lag søknadsutkast from the job detail opens the editor via the toast', async ({ page }) => {
  await page.goto('/jobber?status=interessant')
  await page.getByTestId('job-list').locator('> li').first().click()
  const start = page.getByRole('button', { name: 'Lag søknadsutkast' })
  await start.click()
  await expect(page.getByRole('button', { name: 'Skriver utkast …' })).toBeDisabled()
  await expect(page.getByTestId('task-indicator')).toContainText('Søknadsutkast')

  const toast = page.getByRole('status').filter({ hasText: 'Søknadsutkast ferdig: versjon 1' })
  await expect(toast).toBeVisible({ timeout: 10_000 })
  await expect(page.getByRole('link', { name: 'Åpne søknad' })).toBeVisible()
  await toast.getByRole('button', { name: 'Åpne' }).click()
  await expect(page).toHaveURL(/\/soknader\/\d+$/)
  await expect(textArea(page)).toHaveValue(/Jeg søker på stillingen/)
  await expect(page.getByTestId('editor-toolbar').getByText('Utkast', { exact: true })).toBeVisible()
})
