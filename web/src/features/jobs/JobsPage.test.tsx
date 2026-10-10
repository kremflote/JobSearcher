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
db.runMs = 300
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

const rows = () => within(screen.getByTestId('job-list')).getAllByRole('listitem')

describe('Jobber (FRONTEND §5.2)', () => {
  it('triages with the keyboard, keeps the row dimmed, and undoes with u', async () => {
    const user = userEvent.setup()
    renderAt('/jobber')
    await screen.findByTestId('job-list')
    const first = rows()[0]!
    const id = Number(first.dataset.jobId)

    await user.keyboard('j')
    expect(within(first).getByRole('link')).toHaveAttribute('aria-current', 'true')

    await user.keyboard('i')
    await waitFor(() => expect(first).toHaveAttribute('data-status', 'interessant'))
    expect(db.jobs.find((j) => j.id === id)!.status).toBe('interessant')
    expect(rows()[0]).toBe(first) // stays in place until the list reloads
    expect(await screen.findByRole('status')).toHaveTextContent('Interessant:')
    // Moved on to the next job.
    expect(within(rows()[1]!).getByRole('link')).toHaveAttribute('aria-current', 'true')

    await user.keyboard('u')
    await waitFor(() => expect(first).toHaveAttribute('data-status', 'ny'))
    expect(db.jobs.find((j) => j.id === id)!.status).toBe('ny')
  })

  it('filters by type through the URL', async () => {
    const user = userEvent.setup()
    const router = renderAt('/jobber')
    await screen.findByTestId('job-list')
    await user.click(screen.getByRole('tab', { name: 'Trainee' }))
    expect(router.state.location.search).toBe('?type=trainee')
    await waitFor(() => {
      const ids = rows().map((r) => Number(r.dataset.jobId))
      expect(ids.every((i) => db.jobs.find((j) => j.id === i)!.job_type === 'trainee')).toBe(true)
    })
  })

  it('shows the job detail with match reasons on its own screen below 1024 px', async () => {
    const job = db.jobs.find((j) => j.status === 'ny' && j.description)!
    renderAt(`/jobber/${job.id}`)
    const detail = await screen.findByTestId('job-detail')
    expect(within(detail).getByRole('heading', { name: job.title })).toBeInTheDocument()
    expect(within(detail).getByText('Hvorfor match')).toBeInTheDocument()
    expect(screen.getByTestId('action-bar')).toBeInTheDocument()
  })
})

describe('Kjør nå (FRONTEND §3.3)', () => {
  it('shows the active run and refreshes when it is done', async () => {
    const user = userEvent.setup()
    renderAt('/mer')
    await user.click(await screen.findByRole('button', { name: 'Kjør nå' }))
    await waitFor(() => expect(screen.getByTestId('task-indicator')).toHaveTextContent('Kjøring'))
    await waitFor(() => expect(screen.queryByTestId('task-indicator')).toBeNull(), { timeout: 6000 })
    expect(await screen.findByText(/^Kjøring ferdig/)).toBeInTheDocument()
    expect(db.tasks[0]!.status).toBe('done')
  }, 10_000)
})
