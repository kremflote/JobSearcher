import type { ApplicationStatus } from '@/api/types'
import { STATUS_LABEL } from '@/lib/status'
import { createMockDb } from './db'
import { buildOverview, filterJobs } from './handlers'

const db = createMockDb(new Date(2026, 9, 10, 12))

describe('fixture set (FRONTEND §8)', () => {
  it('has ~40 jobs across all job types', () => {
    expect(db.jobs.length).toBeGreaterThanOrEqual(40)
    const types = new Set(db.jobs.map((j) => j.job_type))
    expect(types).toEqual(new Set(['permanent', 'trainee', 'graduate', 'summer']))
  })

  it('covers every application status', () => {
    const statuses = new Set(db.jobs.map((j) => j.status))
    for (const s of Object.keys(STATUS_LABEL) as ApplicationStatus[]) expect(statuses).toContain(s)
  })

  it('has reposts, title-only jobs, unknown deadlines and discarded jobs', () => {
    expect(db.jobs.some((j) => j.reposted)).toBe(true)
    expect(db.jobs.some((j) => j.ad_text_status === 'missing' && j.description === null)).toBe(true)
    expect(db.jobs.some((j) => j.deadline === null && j.deadline_text)).toBe(true)
    expect(db.discarded.length).toBeGreaterThan(0)
  })

  it('links every non-new job to an application', () => {
    for (const job of db.jobs.filter((j) => j.status !== 'ny')) {
      expect(job.application?.status).toBe(job.status)
      expect(db.applications.cards.find((a) => a.job_id === job.id)).toBeDefined()
    }
  })

  it('uses only invented domains', () => {
    const urls = db.jobs.flatMap((j) => [
      j.application_url,
      ...j.source_refs.map((r) => r.url),
      ...j.contacts.map((c) => c.email),
    ])
    for (const url of urls.filter(Boolean)) {
      expect(url).toMatch(/\.example(\/|$)|^https:\/\/www\.finn\.no\/job\/ad\/\d+$/)
    }
  })
})

describe('mock handlers', () => {
  it('filters by type and min score, sorted by deadline', () => {
    const items = filterJobs(db, new URLSearchParams({ type: 'trainee', min_score: '60' }))
    expect(items.length).toBeGreaterThan(0)
    expect(items.every((j) => j.job_type === 'trainee' && (j.score ?? 0) >= 60)).toBe(true)
    const deadlines = items.map((j) => j.deadline).filter(Boolean) as string[]
    expect(deadlines).toEqual([...deadlines].sort())
  })

  it('builds an overview with upcoming deadlines and follow-ups', () => {
    const o = buildOverview(db)
    expect(o.deadlines.length).toBeGreaterThan(0)
    expect(o.deadlines.every((j) => j.status === 'interessant' || j.status === 'utkast')).toBe(true)
    expect(o.follow_ups.length).toBeGreaterThan(0)
    expect(o.new_since_last.top.length).toBeLessThanOrEqual(5)
    expect(o.sources.some((s) => s.health === 'fail')).toBe(true)
  })
})
