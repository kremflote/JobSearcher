import type { ApplicationCard } from '@/api/types'
import { TRACKER_COLUMNS } from '@/lib/status'
import { dueOf, groupByColumn, legalTargets, sortCards } from './cards'

const card = (over: Partial<ApplicationCard>): ApplicationCard => ({
  id: 1,
  job_id: 1,
  status: 'sokt',
  job_title: 'Utvikler',
  company: 'Eksempel AS',
  deadline: null,
  applied_at: null,
  follow_up_at: null,
  next_step: null,
  next_step_at: null,
  contact_name: null,
  notes: null,
  created_at: '2026-10-01T09:00:00Z',
  allowed_next: [],
  previous_status: null,
  latest_draft_id: null,
  latest_draft_at: null,
  ...over,
})

describe('tracker cards', () => {
  it('counts the deadline only before applying', () => {
    expect(dueOf(card({ status: 'interessant', deadline: '2026-10-12', follow_up_at: '2026-10-20' }))).toBe('2026-10-12')
    expect(dueOf(card({ status: 'sokt', deadline: '2026-10-12', follow_up_at: '2026-10-20' }))).toBe('2026-10-20')
    expect(dueOf(card({ status: 'sokt', deadline: '2026-10-12' }))).toBeNull()
  })

  it('sorts active cards by due date with undated last, closed cards newest first', () => {
    const a = card({ id: 1, next_step_at: '2026-10-15' })
    const b = card({ id: 2 })
    const c = card({ id: 3, follow_up_at: '2026-10-11' })
    expect(sortCards([a, b, c]).map((x) => x.id)).toEqual([3, 1, 2])
    const old = card({ id: 4, status: 'avslag', created_at: '2026-09-01T00:00:00Z' })
    const recent = card({ id: 5, status: 'trukket', created_at: '2026-10-01T00:00:00Z' })
    expect(sortCards([old, recent]).map((x) => x.id)).toEqual([5, 4])
  })

  it('groups closed statuses under Avsluttet and finds legal targets per column', () => {
    const groups = groupByColumn([card({ id: 1, status: 'avslag' }), card({ id: 2, status: 'ikke_aktuell' }), card({ id: 3 })])
    expect(groups.find((g) => g.column.id === 'avsluttet')!.cards).toHaveLength(2)
    const closed = TRACKER_COLUMNS.find((c) => c.id === 'avsluttet')!
    expect(legalTargets(card({ allowed_next: ['intervju', 'avslag', 'trukket'] }), closed)).toEqual(['avslag', 'trukket'])
  })
})
