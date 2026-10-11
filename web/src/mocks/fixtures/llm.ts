/**
 * Invented LLM usage for `GET /api/llm/usage` (FRONTEND §5.1, F2b). One variant per balance state,
 * picked with `?mock_llm=<state>` when the mock app loads (see `mocks/browser.ts`) or by setting
 * `db.llmState` in tests.
 */
import { formatISO, startOfMonth } from 'date-fns'
import type { LlmBackendUsage, LlmDailyUsage, LlmUsage, OpenRouterBalance } from '@/api/types'
import type { Clock } from './time'

export const LLM_STATES = ['account', 'key_limit', 'unknown', 'unset', 'low', 'warn'] as const
export type LlmState = (typeof LLM_STATES)[number]

export const isLlmState = (s: string | null | undefined): s is LlmState => LLM_STATES.includes(s as LlmState)

const CAP_USD = 25
const WARN_RATIO = 0.8
/** Days (relative to today) where `claude -p` failed and calls went to OpenRouter. */
const FALLBACK_DAYS = new Set([-22, -21, -9, -3, 0])
/** Days without any runs. */
const QUIET_DAYS = new Set([-16, -15])

const round = (n: number, d = 4) => Math.round(n * 10 ** d) / 10 ** d

type DayRow = LlmDailyUsage & { calls: number }

function buildDays(c: Clock, withOpenRouter: boolean): DayRow[] {
  const rows: DayRow[] = []
  for (let d = -29; d <= 0; d++) {
    if (QUIET_DAYS.has(d)) continue
    const seed = d + 30
    // Sonnet-like prices for the estimate: $3 / $15 per million tokens.
    const calls = 6 + ((seed * 7) % 9)
    const input = calls * (4800 + ((seed * 373) % 2600))
    const output = calls * (600 + ((seed * 97) % 500))
    rows.push({
      date: c.day(d),
      backend: 'claude_code',
      calls,
      input_tokens: input,
      output_tokens: output,
      cost_usd: round(input * 3e-6 + output * 15e-6),
    })
    if (withOpenRouter && FALLBACK_DAYS.has(d)) {
      // DeepSeek-like prices: $0.27 / $1.10 per million tokens.
      const orCalls = 3 + (seed % 4)
      const orIn = orCalls * 5600
      const orOut = orCalls * 820
      rows.push({
        date: c.day(d),
        backend: 'openrouter',
        calls: orCalls,
        input_tokens: orIn,
        output_tokens: orOut,
        cost_usd: round(orIn * 0.27e-6 + orOut * 1.1e-6),
      })
    }
  }
  return rows
}

function balance(c: Clock, state: LlmState): OpenRouterBalance {
  const fetched_at = new Date(c.now.getTime() - 6 * 60_000).toISOString()
  switch (state) {
    case 'unset':
      return { configured: false, balance_usd: null, total_credits_usd: null, balance_source: null, fetched_at: null }
    case 'unknown':
      return { configured: true, balance_usd: null, total_credits_usd: null, balance_source: null, fetched_at }
    case 'key_limit':
      return { configured: true, balance_usd: 3.85, total_credits_usd: 5, balance_source: 'key_limit', fetched_at }
    case 'low':
      return { configured: true, balance_usd: 0.62, total_credits_usd: 10, balance_source: 'account', fetched_at }
    default:
      return { configured: true, balance_usd: 7.4, total_credits_usd: 10, balance_source: 'account', fetched_at }
  }
}

export function buildLlmUsage(c: Clock, state: LlmState = 'account'): LlmUsage {
  const monthStart = formatISO(startOfMonth(c.now), { representation: 'date' })
  const days = buildDays(c, state !== 'unset')

  const by_backend: LlmBackendUsage[] = (['claude_code', 'openrouter'] as const).map((backend) => {
    const rows = days.filter((r) => r.backend === backend && r.date >= monthStart)
    const sum = (k: 'calls' | 'input_tokens' | 'output_tokens' | 'cost_usd') => rows.reduce((a, r) => a + r[k], 0)
    const calls = sum('calls')
    return {
      backend,
      calls,
      // Every OpenRouter call in the mock is a fallback for claude_code.
      fallback_calls: backend === 'openrouter' ? calls : 0,
      input_tokens: sum('input_tokens'),
      output_tokens: sum('output_tokens'),
      cost_usd: round(sum('cost_usd')),
      estimated: backend === 'claude_code',
    }
  })

  const spent = round(by_backend.reduce((a, b) => a + b.cost_usd, 0), 2)
  // The warn variant lowers the cap so this month's spend sits at ~88 % of it.
  const cap = state === 'warn' ? Math.max(0.01, round(spent / 0.88, 2)) : CAP_USD

  return {
    month_start: monthStart,
    cap_usd: cap,
    spent_usd: spent,
    warn: spent >= cap * WARN_RATIO,
    by_backend,
    daily: days.map(({ calls: _calls, ...row }) => row),
    openrouter: balance(c, state),
  }
}
