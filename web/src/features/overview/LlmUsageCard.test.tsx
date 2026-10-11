import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { createMockDb } from '@/mocks/db'
import { createHandlers } from '@/mocks/handlers'
import { LlmUsageCard } from './LlmUsageCard'

const db = createMockDb()
const server = setupServer(...createHandlers(db))
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  db.llmState = 'account'
})
afterAll(() => server.close())

function renderCard() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <LlmUsageCard />
    </QueryClientProvider>,
  )
  return screen.getByTestId('llm-usage')
}

describe('LLM-forbruk card (FRONTEND §5.1, F2b)', () => {
  it('shows month cost against the cap, the balance and fallback calls', async () => {
    const card = renderCard()
    expect(card.querySelector('[aria-busy="true"]')).not.toBeNull()
    expect(await within(card).findByText('$7,40 igjen av $10')).toBeInTheDocument()
    expect(within(card).getByRole('progressbar', { name: 'Andel av kostnadstaket' })).toBeInTheDocument()
    expect(within(card).getByText(/av \$25 denne måneden/)).toBeInTheDocument()
    expect(within(card).getByText(/Reservekall denne måneden/)).toBeInTheDocument()
    expect(within(card).queryByText('Nærmer seg kostnadstaket.')).toBeNull()
  })

  it('warns near the cap', async () => {
    db.llmState = 'warn'
    const card = renderCard()
    expect(await within(card).findByText('Nærmer seg kostnadstaket.')).toBeInTheDocument()
  })

  it.each([
    ['unset', 'Reserve ikke satt opp'],
    ['unknown', 'Ukjent'],
    ['low', '$0,62 igjen av $10'],
  ] as const)('shows the %s balance', async (state, text) => {
    db.llmState = state
    const card = renderCard()
    expect(await within(card).findByText(text)).toBeInTheDocument()
    expect(within(card).getByTestId('llm-balance')).toHaveAttribute('data-state', state)
  })

  it('shows an error with "Prøv igjen" and recovers', async () => {
    server.use(http.get('/api/llm/usage', () => HttpResponse.json({ detail: 'feil', code: 'x' }, { status: 500 })))
    const user = userEvent.setup()
    const card = renderCard()
    const retry = await within(card).findByRole('button', { name: 'Prøv igjen' })
    server.resetHandlers()
    await user.click(retry)
    expect(await within(card).findByText('$7,40 igjen av $10')).toBeInTheDocument()
  })

  it('opens the detail with per-backend labels, daily bars and the balance source', async () => {
    const user = userEvent.setup()
    const card = renderCard()
    await user.click(await within(card).findByRole('button', { name: /Detaljer/ }))
    const detail = await screen.findByTestId('llm-usage-detail')

    expect(within(within(detail).getByTestId('llm-backend-claude_code')).getByText('estimat, fra abonnementet')).toBeInTheDocument()
    expect(within(within(detail).getByTestId('llm-backend-openrouter')).getByText('betalt')).toBeInTheDocument()
    expect(within(detail).getByText('Kontosaldo (management-nøkkel)')).toBeInTheDocument()

    const bars = within(detail).getAllByTestId('llm-day')
    expect(bars).toHaveLength(30)
    expect(bars.at(-1)).toHaveAttribute('aria-pressed', 'true')

    // Pick a day with OpenRouter fallback calls (fixtures/llm.ts: 3 days ago).
    const fallbackDay = db.clock.day(-3)
    const bar = bars.find((b) => b.dataset.date === fallbackDay)!
    await user.click(bar)
    expect(bar).toHaveAttribute('aria-pressed', 'true')
    const dayDetail = within(detail).getByTestId('llm-day-detail')
    expect(within(dayDetail).getByText('OpenRouter')).toBeInTheDocument()
    expect(within(dayDetail).getByText('Claude-abonnement')).toBeInTheDocument()

    // A quiet day (16 days ago) has no calls.
    await user.click(bars.find((b) => b.dataset.date === db.clock.day(-16))!)
    expect(within(dayDetail).getByText('Ingen kall denne dagen.')).toBeInTheDocument()
  })

  it.each([
    ['unset', 'Reserve ikke satt opp', /OPENROUTER_API_KEY/],
    ['unknown', 'Saldo ukjent', /OPENROUTER_MANAGEMENT_KEY/],
    ['low', '$0,62 igjen av $10', /Under \$1 igjen/],
    ['key_limit', '$3,85 igjen av $5', /Kredittgrense på nøkkelen/],
  ] as const)('shows the %s balance in the detail', async (state, heading, hint) => {
    db.llmState = state
    const user = userEvent.setup()
    const card = renderCard()
    await user.click(await within(card).findByRole('button', { name: /Detaljer/ }))
    const balance = await screen.findByTestId('llm-balance-detail')
    expect(balance).toHaveAttribute('data-state', state === 'key_limit' ? 'ok' : state)
    expect(within(balance).getByText(heading)).toBeInTheDocument()
    expect(balance).toHaveTextContent(hint)
  })
})
