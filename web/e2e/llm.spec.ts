import { expect, test, type Page } from '@playwright/test'

/** LLM-forbruk (FRONTEND §5.1, F2b): card on Oversikt (PC) / Mer (mobile), detail panel or sheet. */

const isMobile = (name: string) => name === 'mobile'
/** The card lives under "Mer" on mobile and on Oversikt from 768 px. */
const home = (name: string, query = '') => (isMobile(name) ? `/mer${query}` : `/${query}`)

async function openDetail(page: Page) {
  await page.getByTestId('llm-usage').getByText('OpenRouter-saldo').click()
  const dialog = page.getByRole('dialog', { name: 'LLM-forbruk' })
  await expect(dialog).toBeVisible()
  return dialog
}

test('card shows cost, balance and fallback calls; detail opens as panel or sheet', async ({ page }, info) => {
  await page.goto(home(info.project.name))
  const card = page.getByTestId('llm-usage')
  await expect(card).toBeVisible()
  await expect(card.getByText('$7,40 igjen av $10')).toBeVisible()
  await expect(card.getByRole('progressbar', { name: 'Andel av kostnadstaket' })).toBeVisible()
  await expect(card.getByText(/Reservekall denne måneden: \d+/)).toBeVisible()

  const dialog = await openDetail(page)
  // Poll: the sheet slides in.
  const edges = async () => {
    const b = (await dialog.boundingBox())!
    return { left: Math.round(b.x), right: Math.round(b.x + b.width), bottom: Math.round(b.y + b.height), width: b.width }
  }
  if (isMobile(info.project.name)) {
    // Action sheet anchored to the bottom, full width.
    await expect.poll(edges).toMatchObject({ left: 0, right: 390, bottom: 844 })
  } else {
    // Side panel on the right.
    await expect.poll(edges).toMatchObject({ right: 1440 })
    expect((await edges()).width).toBeLessThan(500)
  }
  await expect(dialog.getByTestId('llm-backend-claude_code')).toContainText('estimat, fra abonnementet')
  await expect(dialog.getByTestId('llm-backend-openrouter')).toContainText('betalt')
  await expect(dialog.getByTestId('llm-balance-detail')).toContainText('Kontosaldo (management-nøkkel)')

  // Tap a bar: 3 days ago has OpenRouter fallback calls in the fixtures.
  const bars = dialog.getByTestId('llm-day')
  await expect(bars).toHaveCount(30)
  await expect(bars.last()).toHaveAttribute('aria-pressed', 'true')
  await bars.nth(26).click()
  await expect(bars.nth(26)).toHaveAttribute('aria-pressed', 'true')
  await expect(dialog.getByTestId('llm-day-detail')).toContainText('OpenRouter')
  await expect(dialog.getByTestId('llm-day-detail')).toContainText(/inn · .* ut · \$/)

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
})

test('not configured: card and detail say the fallback is not set up', async ({ page }, info) => {
  await page.goto(home(info.project.name, '?mock_llm=unset'))
  const card = page.getByTestId('llm-usage')
  await expect(card.getByText('Reserve ikke satt opp')).toBeVisible()
  await expect(card.getByText('Reservekall denne måneden: 0')).toBeVisible()

  const dialog = await openDetail(page)
  const balance = dialog.getByTestId('llm-balance-detail')
  await expect(balance).toHaveAttribute('data-state', 'unset')
  await expect(balance).toContainText('OPENROUTER_API_KEY')
  await expect(dialog.getByTestId('llm-backend-openrouter')).toContainText('$0,00')
})

test('low balance and warn are flagged', async ({ page }, info) => {
  await page.goto(home(info.project.name, '?mock_llm=low'))
  await expect(page.getByTestId('llm-balance')).toHaveAttribute('data-state', 'low')
  const dialog = await openDetail(page)
  await expect(dialog.getByRole('alert')).toContainText('Under $1 igjen')

  await page.goto(home(info.project.name, '?mock_llm=warn'))
  await expect(page.getByTestId('llm-usage').getByText('Nærmer seg kostnadstaket.')).toBeVisible()
})
