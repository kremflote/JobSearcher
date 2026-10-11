import { expect, test } from '@playwright/test'

/** F4 (FRONTEND §5.6–5.8): Profil, Innstillinger and Logg against the mock, on both viewports. */

test('profile: edit, save, history with restore', async ({ page }) => {
  await page.goto('/profil')
  await expect(page.getByTestId('derived-status')).toContainText('utdatert')
  await page.getByRole('link', { name: /^cv\.md/ }).click()
  await expect(page).toHaveURL(/\/profil\/cv\.md$/)

  const editor = page.getByRole('textbox', { name: 'Innhold i cv.md' })
  await editor.click()
  await editor.press('Control+End')
  await editor.pressSequentially('\n- Sommerjobb, Testfirma AS (2025)')
  await expect(page.getByTestId('save-status')).toHaveText('Ikke lagret')
  await page.getByRole('button', { name: 'Lagre' }).click()
  await expect(page.getByTestId('save-status')).toHaveText('Lagret')

  await page.getByRole('button', { name: 'Historikk' }).click()
  const history = page.getByTestId('profile-history')
  await expect(history.getByRole('button')).toHaveCount(3) // two versions + close
  await history.getByRole('button', { name: /Eldste/ }).click()
  await expect(history.locator('[data-diff="removed"]')).toContainText('Testfirma')
  await history.getByRole('button', { name: 'Gjenopprett' }).click()
  await expect(page).not.toHaveURL(/historikk/)
  await expect(editor).not.toHaveValue(/Testfirma/)
})

test('profile: invalid YAML is refused and the text is kept', async ({ page }) => {
  await page.goto('/profil/profile.yaml')
  const editor = page.getByRole('textbox', { name: 'Innhold i profile.yaml' })
  await editor.click()
  await editor.press('Control+End')
  await editor.pressSequentially('roles: [backend\n')
  await page.getByRole('button', { name: 'Lagre' }).click()
  await expect(page.getByRole('alert')).toContainText('Ugyldig YAML')
  await expect(page.getByTestId('save-status')).toHaveText('Ikke lagret')
  await expect(editor).toHaveValue(/roles: \[backend/)
})

test('profile: new file from template', async ({ page }) => {
  await page.goto('/profil')
  await page.getByRole('button', { name: 'Ny fil i projects' }).click()
  await page.getByRole('textbox', { name: 'Navn på ny fil i projects' }).fill('Min app')
  await expect(page.getByText('Lages som projects/min-app.md fra malen.')).toBeVisible()
  await page.getByRole('button', { name: 'Lag', exact: true }).click()
  await expect(page).toHaveURL(/\/profil\/projects\/min-app\.md$/)
  await expect(page.getByRole('textbox', { name: 'Innhold i projects/min-app.md' })).toHaveValue(/# Prosjektnavn/)
})

test('profile: regenerate, then the derived view shows changes and rescore is offered', async ({ page }) => {
  await page.goto('/profil')
  await page.getByTestId('derived-status').getByRole('button', { name: 'Regenerer' }).click()
  await expect(page.getByTestId('derived-status')).toContainText('oppdatert', { timeout: 10_000 })
  await expect(page.getByTestId('rescore-card')).toContainText('12 aktive jobber')

  await page.getByRole('link', { name: 'Vis destillert' }).click()
  const view = page.getByTestId('derived-view')
  const short = view.getByRole('article', { name: 'profile_short.md' })
  await short.getByRole('tab', { name: 'Endringer' }).click()
  await expect(short.locator('[data-diff="added"]')).toContainText('Oppdatert')
})

test('settings: override, validation and reset', async ({ page }) => {
  await page.goto('/innstillinger')
  const ratio = page.getByTestId('setting-llm.warn_ratio')
  const field = ratio.getByRole('textbox')
  await field.fill('1,5')
  await field.press('Enter')
  await expect(page.getByRole('status')).toContainText('må være mellom 0,1 og 1')
  await expect(field).toHaveValue('0,8')

  await field.fill('0,9')
  await field.press('Enter')
  await expect(ratio.getByText('Standard: 0,8')).toBeVisible()
  await ratio.getByRole('button', { name: /Tilbakestill/ }).click()
  await expect(ratio.getByText('Standard: 0,8')).toHaveCount(0)
  await expect(field).toHaveValue('0,8')

  const nav = page.getByTestId('setting-sources.nav.enabled').getByRole('switch')
  await nav.click()
  await expect(nav).toHaveAttribute('aria-checked', 'false')

  const words = page.getByTestId('setting-search.role_exclude')
  await words.getByRole('textbox').fill('hr, salg')
  await words.getByRole('textbox').press('Enter')
  await expect(words.getByRole('button', { name: 'Fjern salg' })).toBeVisible()
  await words.getByRole('button', { name: 'Fjern pentest' }).click()
  await expect(words.getByRole('button', { name: 'Fjern pentest' })).toHaveCount(0)
})

test('settings: rescore runs as a background task', async ({ page }) => {
  await page.goto('/innstillinger')
  const card = page.getByTestId('rescore-card')
  await expect(card).toContainText('12 aktive jobber')
  await card.getByRole('button', { name: 'Score på nytt' }).click()
  await expect(card).toContainText('Alle aktive jobber er scoret', { timeout: 10_000 })
})

test('logs: tabs, errors and "Vis jobb" for a discarded job', async ({ page }) => {
  await page.goto('/logg')
  await expect(page.getByTestId('run-row').first()).toBeVisible()
  await expect(page.getByText('HTTP 401 fra NAV-feeden: token utløpt?')).toBeVisible()

  await page.getByRole('tab', { name: 'Agentkall' }).click()
  await expect(page).toHaveURL(/fane=agentkall/)
  await expect(page.getByText('Svaret var ikke gyldig JSON (forsøkt på nytt 2 ganger)')).toBeVisible()

  await page.getByRole('tab', { name: 'Forkastet' }).click()
  const row = page.getByTestId('discarded-row').filter({ hasText: 'Senior backend-utvikler' })
  await expect(row).toContainText('Senioritet')
  await row.getByRole('link').click()
  await expect(page).toHaveURL(/\/jobber\/2001$/)
  await expect(page.getByRole('heading', { name: 'Senior backend-utvikler' })).toBeVisible()
})
