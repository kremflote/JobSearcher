import { expect, test, type Locator, type Page } from '@playwright/test'

/** Tracker (FRONTEND §5.4, F2): the whole status flow from mobile; drag and drop on PC. */

const cards = (scope: Page | Locator) => scope.getByTestId('tracker-card')
const card = (page: Page, id: string) => page.locator(`[data-testid="tracker-card"][data-app-id="${id}"]`)

async function moveOnMobile(page: Page, id: string, to: string) {
  await card(page, id).getByRole('button').click()
  const sheet = page.getByTestId('action-sheet')
  await sheet.getByRole('button', { name: to, exact: true }).click()
  await expect(sheet).toBeHidden()
}

test('mobile: whole status flow from Interessant to Tilbud, with notes', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile')
  await page.goto('/tracker')
  const first = cards(page.getByTestId('group-interessant')).first()
  const id = (await first.getAttribute('data-app-id'))!

  for (const [to, group] of [
    ['Utkast', 'utkast'],
    ['Søkt', 'sokt'],
    ['Intervju', 'intervju'],
    ['Tilbud', 'tilbud'],
  ] as const) {
    await moveOnMobile(page, id, to)
    await expect(page.getByTestId(`group-${group}`).locator(`[data-app-id="${id}"]`)).toBeVisible()
  }
  await expect(page.getByRole('status').filter({ hasText: 'Tilbud:' })).toBeVisible()

  // Edit details in the full-screen sheet.
  await card(page, id).getByRole('button').click()
  await page.getByRole('button', { name: 'Neste steg, oppfølging og notater' }).click()
  await expect(page).toHaveURL(new RegExp(`app=${id}`))
  const panel = page.getByTestId('application-panel')
  await panel.getByLabel('Neste steg').fill('Svar innen fredag')
  await panel.getByLabel('Notater').fill('Lønn og startdato avklart.')
  await panel.getByRole('button', { name: 'Lagre' }).click()
  await expect(panel.getByRole('button', { name: 'Lagre' })).toBeDisabled()
  await expect(panel.getByTestId('event-log').locator('li')).toHaveCount(5)

  // Back closes the sheet and the card shows the next step.
  await page.goBack()
  await expect(panel).toBeHidden()
  await expect(card(page, id)).toContainText('Svar innen fredag')
})

test('mobile: closed applications are collapsed and chips filter groups', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile')
  await page.goto('/tracker')
  const closed = page.getByTestId('group-avsluttet')
  await expect(cards(closed)).toHaveCount(0)
  await page.getByRole('group', { name: 'Status' }).getByRole('button', { name: /Avsluttet/ }).click()
  await expect(page).toHaveURL(/vis=avsluttet/)
  await expect(page.getByTestId('group-interessant')).toBeHidden()
  await expect(cards(closed).first()).toBeVisible()
})

test('desktop: drag to a legal column, refuse an illegal one, undo', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop')
  await page.goto('/tracker')
  const from = page.getByTestId('column-interessant')
  const first = cards(from).first()
  const id = (await first.getAttribute('data-app-id'))!

  async function drag(target: Locator) {
    const a = (await card(page, id).boundingBox())!
    const b = (await target.boundingBox())!
    await page.mouse.move(a.x + a.width / 2, a.y + 12)
    await page.mouse.down()
    await page.mouse.move(a.x + a.width / 2 + 10, a.y + 20, { steps: 3 })
    await page.mouse.move(b.x + b.width / 2, b.y + 80, { steps: 10 })
    return async () => page.mouse.up()
  }

  // While dragging, illegal columns are marked and dimmed.
  const drop = await drag(page.getByTestId('column-tilbud'))
  await expect(page.getByTestId('column-tilbud')).toHaveAttribute('data-legal', 'false')
  await expect(page.getByTestId('column-sokt')).toHaveAttribute('data-legal', 'true')
  await drop()
  await expect(page.getByRole('status').filter({ hasText: 'Kan ikke flytte' })).toBeVisible()
  await expect(from.locator(`[data-app-id="${id}"]`)).toBeVisible()

  await (await drag(page.getByTestId('column-sokt')))()
  await expect(page.getByTestId('column-sokt').locator(`[data-app-id="${id}"]`)).toBeVisible()
  await expect(card(page, id)).toContainText('Følg opp')

  await page.getByRole('status').getByRole('button', { name: 'Angre' }).click()
  await expect(from.locator(`[data-app-id="${id}"]`)).toBeVisible()
})

test('desktop: status menu and side panel', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop')
  await page.goto('/tracker')
  const col = page.getByTestId('column-sokt')
  const first = cards(col).first()
  const id = (await first.getAttribute('data-app-id'))!

  await first.getByRole('button', { name: /^Flytt / }).click()
  await page.getByRole('menuitem', { name: 'Intervju' }).click()
  await expect(page.getByTestId('column-intervju').locator(`[data-app-id="${id}"]`)).toBeVisible()

  // The side panel moves status too; closed statuses land in the collapsed Avsluttet column.
  await card(page, id).getByRole('button', { name: /^Åpne / }).click()
  const panel = page.getByTestId('application-panel')
  await expect(panel).toBeVisible()
  await panel.getByRole('button', { name: 'Avslag' }).click()
  await expect(panel).toContainText('Intervju → Avslag')
  await page.keyboard.press('Escape')
  await expect(panel).toBeHidden()

  await page.getByRole('button', { name: /^Vis Avsluttet/ }).click()
  await expect(page.getByTestId('column-avsluttet').locator(`[data-app-id="${id}"]`)).toBeVisible()
})
