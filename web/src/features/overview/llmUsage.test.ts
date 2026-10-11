import type { LlmUsage, OpenRouterBalance } from '@/api/types'
import { buildLlmUsage, LLM_STATES } from '@/mocks/fixtures/llm'
import { clock } from '@/mocks/fixtures/time'
import { balanceState, balanceText, capPercent, dailySeries, dayLabel, fallbackCalls, tokens, usd } from './llmUsage'

const NBSP = ' '
const today = new Date(2026, 9, 11, 12)

const bal = (b: Partial<OpenRouterBalance>): OpenRouterBalance => ({
  configured: true,
  balance_usd: 7.4,
  total_credits_usd: 10,
  used_usd: 2.6,
  balance_source: 'account',
  fetched_at: null,
  ...b,
})

describe('usd', () => {
  it.each([
    [7.4, {}, '$7,40'],
    [0, {}, '$0,00'],
    [0.004, {}, '< $0,01'],
    [10, { whole: true }, '$10'],
    [10.5, { whole: true }, '$10,50'],
    [1234.5, {}, `$1${NBSP}234,50`],
  ] as const)('%d → %s', (n, opts, out) => {
    expect(usd(n, opts)).toBe(out)
  })
})

describe('tokens', () => {
  it.each([
    [950, '950'],
    [12_345, '12,3k'],
    [1000, '1k'],
    [1_234_567, '1,2 mill.'],
  ])('%i → %s', (n, out) => {
    expect(tokens(n)).toBe(out)
  })
})

describe('capPercent', () => {
  it('rounds and clamps', () => {
    expect(capPercent(4.37, 25)).toBe(17)
    expect(capPercent(30, 25)).toBe(100)
    expect(capPercent(1, 0)).toBe(100)
  })
})

describe('balanceState and balanceText', () => {
  it('is unset without a key', () => {
    const b = bal({ configured: false, balance_usd: null, total_credits_usd: null, balance_source: null })
    expect(balanceState(b)).toBe('unset')
    expect(balanceText(b)).toBeNull()
  })

  it('is unknown with a key but no source', () => {
    const b = bal({ balance_usd: null, total_credits_usd: null, balance_source: null })
    expect(balanceState(b)).toBe('unknown')
    expect(balanceText(b)).toBeNull()
  })

  it('is low under $1', () => {
    expect(balanceState(bal({ balance_usd: 0.99 }))).toBe('low')
    expect(balanceState(bal({ balance_usd: 1 }))).toBe('ok')
  })

  it('formats "igjen av"', () => {
    expect(balanceText(bal({}))).toBe('$7,40 igjen av $10')
    expect(balanceText(bal({ balance_source: 'key_limit', balance_usd: 3.85, total_credits_usd: 5 }))).toBe('$3,85 igjen av $5')
    expect(balanceText(bal({ total_credits_usd: null }))).toBe('$7,40 igjen')
  })
})

describe('dailySeries', () => {
  it('fills 30 days ending today, oldest first, with totals per day', () => {
    const daily: LlmUsage['daily'] = [
      { date: '2026-10-11', backend: 'openrouter', input_tokens: 100, output_tokens: 10, cost_usd: 0.001 },
      { date: '2026-10-11', backend: 'claude_code', input_tokens: 1000, output_tokens: 200, cost_usd: 0.1 },
      { date: '2026-09-01', backend: 'claude_code', input_tokens: 5, output_tokens: 5, cost_usd: 0 },
    ]
    const s = dailySeries(daily, today)
    expect(s).toHaveLength(30)
    expect(s[0]!.date).toBe('2026-09-12')
    expect(s.at(-1)).toMatchObject({ date: '2026-10-11', total: 1310 })
    // Stacking order: claude_code at the bottom.
    expect(s.at(-1)!.rows.map((r) => r.backend)).toEqual(['claude_code', 'openrouter'])
    expect(s[0]!.rows).toEqual([])
  })

  it('labels days in Norwegian', () => {
    expect(dayLabel('2026-10-11')).toBe('11. okt')
  })
})

describe('mock fixtures (F2b)', () => {
  const c = clock(today)

  it('covers every balance state', () => {
    const states = LLM_STATES.map((s) => balanceState(buildLlmUsage(c, s).openrouter))
    expect(new Set(states)).toEqual(new Set(['ok', 'unknown', 'unset', 'low']))
    expect(buildLlmUsage(c, 'account').openrouter.balance_source).toBe('account')
    expect(buildLlmUsage(c, 'key_limit').openrouter.balance_source).toBe('key_limit')
  })

  it('warns only in the warn variant', () => {
    for (const s of LLM_STATES) expect(buildLlmUsage(c, s).warn).toBe(s === 'warn')
  })

  it('has both backends, 30 days of rows and fallback calls', () => {
    const u = buildLlmUsage(c)
    expect(u.month_start).toBe('2026-10-01')
    expect(u.by_backend.map((b) => b.backend)).toEqual(['claude_code', 'openrouter'])
    expect(u.daily.every((r) => r.date >= '2026-09-12' && r.date <= '2026-10-11')).toBe(true)
    expect(fallbackCalls(u)).toBeGreaterThan(0)
    // The cap counts paid calls only (not the Claude subscription's estimate).
    expect(u.spent_usd).toBeCloseTo(u.by_backend.filter((b) => !b.estimated).reduce((a, b) => a + b.cost_usd, 0), 2)
  })

  it('has no OpenRouter usage when the fallback is not set up', () => {
    const u = buildLlmUsage(c, 'unset')
    expect(u.daily.some((r) => r.backend === 'openrouter')).toBe(false)
    expect(fallbackCalls(u)).toBe(0)
  })
})
