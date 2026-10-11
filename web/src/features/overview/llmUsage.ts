/** Formatting and state logic for the LLM-forbruk card (FRONTEND §5.1, F2b). */
import { addDays, format, formatISO, parseISO, startOfDay } from 'date-fns'
import { nb as nbLocale } from 'date-fns/locale'
import type { LlmBackendName, LlmDailyUsage, LlmUsage, OpenRouterBalance } from '@/api/types'

const nb = (n: number, digits: number) =>
  n.toLocaleString('nb-NO', { minimumFractionDigits: digits, maximumFractionDigits: digits })

/**
 * Dollars with Norwegian number formatting: "$7,40", "$1 234,50". Whole amounts drop the
 * decimals when `whole` is set ("$10"); amounts between 0 and one cent show as "< $0,01".
 */
export function usd(n: number, { whole = false } = {}) {
  if (n > 0 && n < 0.005) return '< $0,01'
  if (whole && Number.isInteger(n)) return `$${nb(n, 0)}`
  return `$${nb(n, 2)}`
}

/** Token counts: "950", "12,3k", "1,2 mill.". */
export function tokens(n: number) {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return `${(Math.round(n / 100) / 10).toLocaleString('nb-NO')}k`
  return `${(Math.round(n / 100_000) / 10).toLocaleString('nb-NO')} mill.`
}

/** Grouped integer: "12 345". */
export const count = (n: number) => n.toLocaleString('nb-NO')

/** Share of the cap in whole percent, clamped to 0–100 for the bar. */
export function capPercent(spent: number, cap: number) {
  if (cap <= 0) return 100
  return Math.max(0, Math.min(100, Math.round((spent / cap) * 100)))
}

export type BalanceState = 'unset' | 'unknown' | 'low' | 'ok'

/** Balance below this many dollars triggers a warning. */
export const LOW_BALANCE_USD = 1

export function balanceState(b: OpenRouterBalance): BalanceState {
  if (!b.configured) return 'unset'
  if (b.balance_source === null || b.balance_usd === null) return 'unknown'
  return b.balance_usd < LOW_BALANCE_USD ? 'low' : 'ok'
}

/** "$7,40 igjen av $10" (or without "av …" when the total is unknown). Null without a known balance. */
export function balanceText(b: OpenRouterBalance) {
  if (b.balance_usd === null || !b.configured || b.balance_source === null) return null
  const of = b.total_credits_usd !== null ? ` av ${usd(b.total_credits_usd, { whole: true })}` : ''
  return `${usd(b.balance_usd)} igjen${of}`
}

export const BALANCE_SOURCE_LABEL: Record<NonNullable<OpenRouterBalance['balance_source']>, string> = {
  account: 'Kontosaldo (management-nøkkel)',
  key_limit: 'Kredittgrense på nøkkelen',
}

/** Calls made as a fallback for another backend this month. */
export const fallbackCalls = (u: LlmUsage) => u.by_backend.reduce((a, b) => a + b.fallback_calls, 0)

export const BACKEND_LABEL: Record<LlmBackendName, string> = {
  claude_code: 'Claude-abonnement',
  openrouter: 'OpenRouter',
  mock: 'Mock',
}

/** Bar colour per backend (theme tokens, so it works in light and dark mode). */
export const BACKEND_COLOR: Record<LlmBackendName, string> = {
  claude_code: 'bg-info',
  openrouter: 'bg-violet',
  mock: 'bg-muted-foreground',
}

/** Stacking order, bottom to top. */
export const BACKEND_ORDER: LlmBackendName[] = ['claude_code', 'openrouter', 'mock']

export type DayUsage = {
  date: string
  /** Total tokens (in + out) for the day across backends. */
  total: number
  rows: LlmDailyUsage[]
}

/** The last `days` days ending today (oldest first), with empty days filled in. */
export function dailySeries(daily: LlmDailyUsage[], today = new Date(), days = 30): DayUsage[] {
  const start = startOfDay(today)
  return Array.from({ length: days }, (_, i) => {
    const date = formatISO(addDays(start, i - days + 1), { representation: 'date' })
    const rows = daily
      .filter((r) => r.date === date)
      .sort((a, b) => BACKEND_ORDER.indexOf(a.backend) - BACKEND_ORDER.indexOf(b.backend))
    return { date, total: rows.reduce((a, r) => a + r.input_tokens + r.output_tokens, 0), rows }
  })
}

/** "11. okt" for bar labels. */
export const dayLabel = (iso: string) => format(parseISO(iso), 'd. MMM', { locale: nbLocale }).replace(/\.$/, '')
