import { expect, test, type Page } from '@playwright/test'

/** Triage of a mock day (FRONTEND §8, F1): swipe on mobile, keyboard on PC. */

const list = (page: Page) => page.getByTestId('job-list')
const rows = (page: Page) => list(page).locator('> li')

async function swipe(page: Page, row: ReturnType<Page['locator']>, dir: 'left' | 'right') {
  const box = (await row.boundingBox())!
  const y = box.y + box.height / 2
  const from = box.x + box.width / 2
  const to = from + (dir === 'right' ? 1 : -1) * box.width * 0.45
  await page.mouse.move(from, y)
  await page.mouse.down()
  for (let i = 1; i <= 8; i++) await page.mouse.move(from + ((to - from) * i) / 8, y)
  await page.mouse.up()
}

test('mobile: triage by swipe with undo, then open the detail', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile')
  await page.goto('/jobber')
  await expect(rows(page).first()).toBeVisible()

  const first = rows(page).nth(0)
  const second = rows(page).nth(1)
  await swipe(page, first, 'right')
  await expect(first).toHaveAttribute('data-status', 'interessant')
  await expect(page).toHaveURL('/jobber') // a swipe is not a tap
  await expect(page.getByRole('status').filter({ hasText: 'Interessant:' })).toBeVisible()

  await swipe(page, second, 'left')
  await expect(second).toHaveAttribute('data-status', 'ikke_aktuell')

  await page.getByRole('button', { name: 'Angre' }).click()
  await expect(second).toHaveAttribute('data-status', 'ny')

  // Tap opens the detail screen with the fixed action bar.
  const thirdId = await rows(page).nth(2).getAttribute('data-job-id')
  const fourthId = await rows(page).nth(3).getAttribute('data-job-id')
  const fifthId = await rows(page).nth(4).getAttribute('data-job-id')
  await rows(page).nth(2).getByRole('link').click()
  await expect(page).toHaveURL(`/jobber/${thirdId}`)
  const bar = page.getByTestId('action-bar')
  await expect(bar).toBeVisible()

  // Triage in the detail goes straight on to the next job in the list.
  await bar.getByRole('button', { name: 'Ikke aktuell' }).click()
  await expect(page).toHaveURL(`/jobber/${fourthId}`)
  await bar.getByRole('button', { name: 'Interessant' }).click()
  await expect(page).toHaveURL(`/jobber/${fifthId}`)

  // The undo toast sits above the action bar, not on top of the buttons.
  const toast = page.getByRole('status').filter({ hasText: 'Interessant:' })
  await expect(toast).toBeVisible()
  const barTop = (await bar.boundingBox())!.y
  // Polled: the toast slides in from below.
  await expect.poll(async () => { const t = (await toast.boundingBox())!; return t.y + t.height }).toBeLessThanOrEqual(barTop)

  // Angre returns to the job that was undone.
  await toast.getByRole('button', { name: 'Angre' }).click()
  await expect(page).toHaveURL(`/jobber/${fourthId}`)

  // Tilbake returns to the list, with the triage shown on the rows.
  await page.getByRole('button', { name: 'Tilbake' }).click()
  await expect(page).toHaveURL('/jobber')
  await expect(rows(page).nth(2)).toHaveAttribute('data-status', 'ikke_aktuell')
  await expect(rows(page).nth(3)).toHaveAttribute('data-status', 'ny')
})

test('mobile: filters live in a sheet and in the URL', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile')
  await page.goto('/jobber')
  await page.getByRole('tab', { name: 'Trainee' }).click()
  await expect(page).toHaveURL('/jobber?type=trainee')
  await page.getByRole('button', { name: /^Filtre/ }).click()
  await page.getByRole('dialog').getByLabel('Min. score').selectOption('60')
  await page.getByRole('button', { name: 'Vis jobber' }).click()
  await expect(page).toHaveURL('/jobber?type=trainee&min_score=60')
  await expect(page.getByRole('button', { name: 'Filtre (1 aktive)' })).toBeVisible()
})

test('PC: triage with the keyboard in master-detail', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop')
  await page.goto('/jobber')
  await expect(rows(page).first()).toBeVisible()
  await expect(page.getByTestId('filter-row')).toBeVisible()

  await page.keyboard.press('j')
  const firstId = await rows(page).first().getAttribute('data-job-id')
  await expect(page).toHaveURL(`/jobber/${firstId}`)
  await expect(page.getByTestId('detail-pane').getByTestId('job-detail')).toBeVisible()

  await page.keyboard.press('i')
  await expect(rows(page).first()).toHaveAttribute('data-status', 'interessant')
  const secondId = await rows(page).nth(1).getAttribute('data-job-id')
  await expect(page).toHaveURL(`/jobber/${secondId}`) // jumped to the next job

  await page.keyboard.press('x')
  await expect(rows(page).nth(1)).toHaveAttribute('data-status', 'ikke_aktuell')

  await page.keyboard.press('u')
  await expect(rows(page).nth(1)).toHaveAttribute('data-status', 'ny')
  await expect(page).toHaveURL(`/jobber/${secondId}`)

  await page.keyboard.press('k')
  await expect(page).toHaveURL(`/jobber/${firstId}`)

  // Buttons in the detail pane do the same as the keys.
  await page.getByTestId('detail-pane').getByRole('button', { name: 'Interessant' }).click()
  await expect(rows(page).first()).toHaveAttribute('data-status', 'ny')
})

test('Oversikt: deadlines, new jobs and "Kjør nå"', async ({ page }, info) => {
  await page.goto(info.project.name === 'mobile' ? '/mer' : '/')
  if (info.project.name === 'desktop') {
    await expect(page.getByTestId('deadlines').getByRole('listitem').first()).toBeVisible()
    await expect(page.getByTestId('new-since').locator('visible=true')).toContainText('Nye siden sist')
  }
  await page.getByRole('button', { name: 'Kjør nå' }).locator('visible=true').click()
  await expect(page.getByTestId('task-indicator')).toContainText('Kjøring')
  await expect(page.getByRole('status').filter({ hasText: /^Kjøring ferdig/ })).toBeVisible({ timeout: 12_000 })
})
