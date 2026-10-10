import { createMockDb } from './db'
import { patchApplication, setTriageStatus, tick, toCard } from './handlers'

const fresh = () => createMockDb(new Date(2026, 9, 10, 12))

describe('mock triage (PUT /api/jobs/{id}/status)', () => {
  it('creates an application on triage and removes it on undo', () => {
    const db = fresh()
    const job = db.jobs.find((j) => j.status === 'ny')!
    const before = db.applications.cards.length

    const res = setTriageStatus(db, job, 'interessant')!
    expect(res.status).toBe('interessant')
    expect(job.application?.id).toBe(res.application_id)
    expect(db.applications.cards).toHaveLength(before + 1)
    expect(db.applications.events.get(res.application_id!)).toHaveLength(1)

    setTriageStatus(db, job, 'ikke_aktuell')
    expect(db.applications.cards.find((a) => a.id === res.application_id)?.status).toBe('ikke_aktuell')
    expect(db.applications.events.get(res.application_id!)).toHaveLength(2)

    expect(setTriageStatus(db, job, 'ny')).toMatchObject({ status: 'ny', application_id: null })
    expect(job.application).toBeNull()
    expect(db.applications.cards).toHaveLength(before)
  })

  it('refuses to triage jobs that are further along', () => {
    const db = fresh()
    const job = db.jobs.find((j) => j.status === 'sokt')!
    expect(setTriageStatus(db, job, 'ikke_aktuell')).toBeNull()
    expect(job.status).toBe('sokt')
  })
})

describe('mock application PATCH (ARCHITECTURE §9.1)', () => {
  const cardWith = (db: ReturnType<typeof fresh>, status: string) => db.applications.cards.find((a) => a.status === status)!

  it('moves along a legal transition, logs it and keeps the job in sync', () => {
    const db = fresh()
    const card = cardWith(db, 'interessant')
    const events = db.applications.events.get(card.id)!.length

    expect(patchApplication(db, card, { status: 'sokt', comment: 'Sendt via Finn' })).toBe(card)
    expect(card.status).toBe('sokt')
    expect(card.applied_at).not.toBeNull()
    expect(card.follow_up_at).toBe(db.clock.day(14))
    expect(db.applications.events.get(card.id)!.at(-1)).toMatchObject({
      from_status: 'interessant',
      to_status: 'sokt',
      comment: 'Sendt via Finn',
    })
    expect(db.applications.events.get(card.id)).toHaveLength(events + 1)
    const job = db.jobs.find((j) => j.id === card.job_id)!
    expect(job.status).toBe('sokt')
    expect(job.application?.status).toBe('sokt')
    expect(toCard(db, card)).toMatchObject({ allowed_next: ['intervju', 'avslag', 'trukket'], previous_status: 'interessant' })
  })

  it('refuses illegal transitions and leaves the card alone', () => {
    const db = fresh()
    const card = cardWith(db, 'interessant')
    expect(patchApplication(db, card, { status: 'tilbud' })).toBeNull()
    expect(patchApplication(db, cardWith(db, 'avslag'), { status: 'intervju' })).toBeNull()
    expect(card.status).toBe('interessant')
  })

  it('undoes the latest move by going back to previous_status', () => {
    const db = fresh()
    const card = cardWith(db, 'interessant')
    const events = db.applications.events.get(card.id)!.length
    patchApplication(db, card, { status: 'sokt' })
    expect(patchApplication(db, card, { status: 'interessant', follow_up_at: null })).toBe(card)
    expect(card).toMatchObject({ status: 'interessant', applied_at: null, follow_up_at: null })
    expect(db.applications.events.get(card.id)).toHaveLength(events)
    // The first event (from `ny`) is triage's to undo, not the tracker's.
    expect(toCard(db, card).previous_status).toBeNull()
  })

  it('changes only the fields that are present', () => {
    const db = fresh()
    const card = cardWith(db, 'intervju')
    const before = { ...card }
    patchApplication(db, card, { notes: 'Nytt notat', next_step_at: null })
    expect(card).toEqual({ ...before, notes: 'Nytt notat', next_step_at: null })
  })
})

describe('mock run task', () => {
  it('progresses with the clock and finishes by updating sources', () => {
    const db = fresh()
    const created = Date.parse('2026-10-10T10:00:00Z')
    const task = {
      id: 't1',
      kind: 'run' as const,
      status: 'queued' as const,
      progress: 0,
      message: null,
      created_at: new Date(created).toISOString(),
      finished_at: null,
      result: null,
    }
    expect(tick(db, task, created + db.runMs / 2)).toMatchObject({ status: 'running', progress: 0.5 })
    const done = tick(db, task, created + db.runMs)
    expect(done.status).toBe('done')
    expect(db.lastRunAt).toBe(done.finished_at)
    expect(db.sources.filter((s) => s.source !== 'manual').every((s) => s.last_run_at === done.finished_at)).toBe(true)
  })
})
