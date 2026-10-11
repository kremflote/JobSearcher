import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { setupServer } from 'msw/node'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { ThemeProvider } from '@/lib/theme'
import { createHandlers } from '@/mocks/handlers'
import { routes } from '@/routes'

const server = setupServer(...createHandlers())
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterAll(() => server.close())

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(
    <ThemeProvider>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>,
  )
  return router
}

describe('AppShell', () => {
  it('renders sidebar and bottom tabs with the same routes', () => {
    renderAt('/')
    const [sidebar, tabs] = screen.getAllByRole('navigation', { name: 'Hovedmeny' })
    expect(within(sidebar!).getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual([
      '/',
      '/jobber',
      '/tracker',
      '/soknader',
      '/profil',
      '/innstillinger',
      '/logg',
    ])
    expect(within(tabs!).getAllByRole('link').map((a) => a.textContent)).toEqual(['Oversikt', 'Jobber', 'Tracker', 'Mer'])
  })

  it('navigates and loads data through the typed client', async () => {
    const router = renderAt('/')
    const [sidebar] = screen.getAllByRole('navigation', { name: 'Hovedmeny' })
    await userEvent.click(within(sidebar!).getByRole('link', { name: 'Jobber' }))
    expect(router.state.location.pathname).toBe('/jobber')
    expect(await screen.findByText(/^\d+ jobber$/)).toBeInTheDocument()
  })

  it('shows the remaining pages under "Mer"', async () => {
    renderAt('/mer')
    const main = await screen.findByRole('main')
    expect(within(main).getAllByRole('link').map((a) => a.textContent)).toEqual([
      'Søknader',
      'Profil',
      'Innstillinger',
      'Logg',
    ])
  })
})
