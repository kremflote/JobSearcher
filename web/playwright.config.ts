import { defineConfig, devices } from '@playwright/test'

const PORT = 5174

/** E2E against `dev:mock` at the two viewports from FRONTEND §4.1. */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    locale: 'nb-NO',
    timezoneId: 'Europe/Oslo',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'mobile',
      use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: {
    command: `npm run dev:mock -- --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
  },
})
