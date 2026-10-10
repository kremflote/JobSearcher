import { differenceInCalendarDays, format, parseISO } from 'date-fns'
import { nb } from 'date-fns/locale'

export type Tone = 'good' | 'warn' | 'bad' | 'neutral' | 'muted'

/** Score colour (FRONTEND §6): ≥ 70 green, 50–69 neutral, < 50 muted. */
export function scoreTone(score: number): Tone {
  if (score >= 70) return 'good'
  if (score >= 50) return 'neutral'
  return 'muted'
}

export type DeadlineInfo = {
  /** Short relative text, e.g. "om 3 d", "i dag", "utløpt". */
  relative: string
  /** Full date, e.g. "14. okt. 2026". Null when unknown. */
  date: string | null
  tone: Tone
  days: number | null
}

/** Deadline colour and text (FRONTEND §6): ≤ 3 d red, ≤ 7 d yellow, ≤ 14 d neutral, unknown "—". */
export function deadlineInfo(deadline: string | null, deadlineText?: string | null, today = new Date()): DeadlineInfo {
  if (!deadline) return { relative: deadlineText ?? '—', date: null, tone: 'muted', days: null }
  const d = parseISO(deadline)
  const days = differenceInCalendarDays(d, today)
  const date = format(d, 'd. MMM yyyy', { locale: nb })
  let relative: string
  if (days < 0) relative = 'utløpt'
  else if (days === 0) relative = 'i dag'
  else if (days === 1) relative = 'i morgen'
  else relative = `om ${days} d`
  const tone: Tone = days < 0 ? 'muted' : days <= 3 ? 'bad' : days <= 7 ? 'warn' : 'neutral'
  return { relative, date, tone, days }
}
