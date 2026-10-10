import type { ApplicationCard } from '@/api/types'
import { CLOSED_STATUSES, TRACKER_COLUMNS, type TrackerColumn } from '@/lib/status'

/** Statuses where the ad's deadline still matters (not applied yet). */
const BEFORE_APPLYING = ['interessant', 'utkast']

/** The date the card is waiting on: next step, follow-up or (before applying) the deadline. */
export function dueOf(card: ApplicationCard): string | null {
  const dates = [card.next_step_at, card.follow_up_at]
  if (BEFORE_APPLYING.includes(card.status)) dates.push(card.deadline)
  return dates.filter((d): d is string => !!d).sort()[0] ?? null
}

/** Active columns: soonest due first, undated last. Closed: newest first. */
export function sortCards(cards: ApplicationCard[]): ApplicationCard[] {
  return [...cards].sort((a, b) => {
    if (CLOSED_STATUSES.includes(a.status)) return a.created_at < b.created_at ? 1 : -1
    const da = dueOf(a)
    const db = dueOf(b)
    if (da !== db) {
      if (!da) return 1
      if (!db) return -1
      return da < db ? -1 : 1
    }
    return a.created_at < b.created_at ? -1 : 1
  })
}

export function groupByColumn(cards: ApplicationCard[]): { column: TrackerColumn; cards: ApplicationCard[] }[] {
  return TRACKER_COLUMNS.map((column) => ({
    column,
    cards: sortCards(cards.filter((c) => column.statuses.includes(c.status))),
  }))
}

/** Statuses in `column` the card may move to (ARCHITECTURE §9.1, served as `allowed_next`). */
export const legalTargets = (card: ApplicationCard, column: TrackerColumn) =>
  column.statuses.filter((s) => card.allowed_next.includes(s))
