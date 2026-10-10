import { expect, test } from '@playwright/test'

const isMobile = (name: string) => name === 'mobile'

test('navigates between all pages', async ({ page }, info) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: 'Oversikt' })).toBeVisible()
  await expect(page.getByTestId('deadlines')).toContainText('Frister neste 14 dager')

  const nav = page.getByRole('navigation', { name: 'Hovedmeny' }).locator('visible=true')
  await expect(nav).toHaveCount(1)

  if (isMobile(info.project.name)) {
    await nav.getByRole('link', { name: 'Jobber' }).click()
    await expect(page).toHaveURL('/jobber')
    await expect(page.getByTestId('job-count')).toHaveText(/^\d+ jobber$/)

    await nav.getByRole('link', { name: 'Tracker' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Tracker' })).toBeVisible()

    for (const label of ['Søknader', 'Profil', 'Innstillinger', 'Logg']) {
      await nav.getByRole('link', { name: 'Mer' }).click()
      await page.getByRole('main').getByRole('link', { name: label }).click()
      await expect(page.getByRole('heading', { level: 1, name: label })).toBeVisible()
    }
  } else {
    for (const label of ['Jobber', 'Tracker', 'Søknader', 'Profil', 'Innstillinger', 'Logg', 'Oversikt']) {
      await nav.getByRole('link', { name: label }).click()
      await expect(page.getByRole('heading', { level: 1, name: label })).toBeVisible()
    }
  }
})

test('uses bottom tabs on mobile and a sidebar on PC', async ({ page }, info) => {
  await page.goto('/')
  // CSS locators: getByRole skips the nav that is display:none at this width.
  const navs = page.locator('nav[aria-label="Hovedmeny"]')
  await expect(navs).toHaveCount(2)
  const [sidebar, tabs] = [navs.first(), navs.last()]
  if (isMobile(info.project.name)) {
    await expect(sidebar).toBeHidden()
    await expect(tabs).toBeVisible()
    const box = await tabs.boundingBox()
    expect(box!.y + box!.height).toBeCloseTo(844, 0)
  } else {
    await expect(sidebar).toBeVisible()
    await expect(tabs).toBeHidden()
    await expect(sidebar.getByText('Jobbsøk')).toBeVisible()
  }
})

test('switches theme and remembers it', async ({ page }, info) => {
  await page.goto(isMobile(info.project.name) ? '/mer' : '/')
  await page.getByRole('button', { name: /^Tema:/ }).locator('visible=true').click()
  await page.getByRole('menuitemradio', { name: 'Mørk' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.reload()
  await expect(page.locator('html')).toHaveClass(/dark/)
})

test('serves an installable PWA manifest', async ({ request }) => {
  const res = await request.get('/manifest.webmanifest')
  expect(res.ok()).toBe(true)
  const manifest = await res.json()
  expect(manifest).toMatchObject({ name: 'Jobbsøk', display: 'standalone', start_url: '/' })
  for (const icon of manifest.icons) expect((await request.get(icon.src)).ok()).toBe(true)
})
