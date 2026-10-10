import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { setupServer } from 'msw/node'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { ThemeProvider } from '@/lib/theme'
import { createMockDb } from '@/mocks/db'
import { createHandlers } from '@/mocks/handlers'
import { routes } from '@/routes'

const db = createMockDb()
const server = setupServer(...createHandlers(db))
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

const group = (id: string) => screen.getByTestId(`group-${id}`)

describe('Tracker on mobile (FRONTEND §5.4)', () => {
  it('moves a card through the action sheet and undoes it', async () => {
    const user = userEvent.setup()
    renderAt('/tracker')
    await screen.findByTestId('group-interessant')
    const card = within(group('interessant')).getAllByTestId('tracker-card')[0]!
    const id = card.dataset.appId!

    await user.click(within(card).getByRole('button'))
    const sheet = await screen.findByTestId('action-sheet')
    // Only legal next statuses are offered.
    expect(within(sheet).queryByRole('button', { name: 'Tilbud' })).toBeNull()
    await user.click(within(sheet).getByRole('button', { name: 'Søkt' }))

    await waitFor(() => expect(group('sokt').querySelector(`[data-app-id="${id}"]`)).not.toBeNull())
    expect(db.applications.cards.find((a) => a.id === Number(id))!.status).toBe('sokt')

    await user.click(await screen.findByRole('button', { name: 'Angre' }))
    await waitFor(() => expect(group('interessant').querySelector(`[data-app-id="${id}"]`)).not.toBeNull())
    expect(db.applications.cards.find((a) => a.id === Number(id))!.status).toBe('interessant')
  })

  it('keeps Avsluttet collapsed until opened', async () => {
    const user = userEvent.setup()
    renderAt('/tracker')
    const header = await within(await screen.findByTestId('group-avsluttet')).findByRole('button', { expanded: false })
    expect(within(group('avsluttet')).queryAllByTestId('tracker-card')).toHaveLength(0)
    await user.click(header)
    expect(within(group('avsluttet')).getAllByTestId('tracker-card').length).toBeGreaterThan(0)
  })

  it('edits next step in the panel and saves only that field', async () => {
    const user = userEvent.setup()
    const target = db.applications.cards.find((a) => a.status === 'sokt')!
    const router = renderAt(`/tracker?app=${target.id}`)
    const panel = await screen.findByTestId('application-panel')
    const save = within(panel).getByRole('button', { name: 'Lagre' })
    expect(save).toBeDisabled()

    await user.type(within(panel).getByLabelText('Neste steg'), 'Ring rekrutterer')
    await user.click(save)
    await waitFor(() => expect(target.next_step).toBe('Ring rekrutterer'))
    expect(await within(panel).findByTestId('event-log')).toHaveTextContent('Søkt')

    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Lukk' }))
    await waitFor(() => expect(router.state.location.search).toBe(''))
  })
})
