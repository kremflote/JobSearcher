/**
 * Fixture dates are relative to the moment the mock database is built, so deadlines
 * and "new since last run" stay meaningful whenever the mock app is opened.
 */
import { addDays, formatISO, setHours, setMinutes, startOfDay } from 'date-fns'

export function clock(now = new Date()) {
  const today = startOfDay(now)
  return {
    now,
    /** ISO date (yyyy-MM-dd) `n` days from today. */
    day: (n: number) => formatISO(addDays(today, n), { representation: 'date' }),
    /** ISO datetime `n` days from today at hh:mm local time. */
    at: (n: number, hh = 7, mm = 0) => setMinutes(setHours(addDays(today, n), hh), mm).toISOString(),
  }
}

export type Clock = ReturnType<typeof clock>
