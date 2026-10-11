/**
 * MSW handlers for the v0 contract (FRONTEND §7). Read endpoints are served from the
 * fixtures; mutations are added per wave (F1: triage, runs, tasks; F2: applications; F3: drafts). Anything else under /api
 * gets the contract's 501.
 */
import { addDays, parseISO } from 'date-fns'
import { http, HttpResponse } from 'msw'
import type { components } from '@/api/schema'
import type { ApplicationStatus, JobDetail, JobListItem, JobType, Task } from '@/api/types'
import { CLOSED_STATUSES } from '@/lib/status'
import { createMockDb, toListItem, type MockDb } from './db'
import { markdownToDocx } from './docx'
import { saveUserDraft, startDraft, startRevise } from './drafts'
import type { MockCard } from './fixtures/applications'
import { buildLlmUsage } from './fixtures/llm'

type S = components['schemas']

const json = <T,>(data: T, init?: ResponseInit) => HttpResponse.json(data as never, init)
const error = (status: number, code: string, detail: string) =>
  HttpResponse.json({ detail, code } satisfies S['ErrorResponse'], { status })

function byDeadlineThenScore(a: JobListItem, b: JobListItem) {
  if (a.deadline !== b.deadline) {
    if (!a.deadline) return 1
    if (!b.deadline) return -1
    return a.deadline < b.deadline ? -1 : 1
  }
  return (b.score ?? -1) - (a.score ?? -1)
}

export function filterJobs(db: MockDb, params: URLSearchParams): JobListItem[] {
  const today = db.clock.day(0)
  const type = params.get('type') as JobType | null
  const status = params.get('status') as ApplicationStatus | null
  const minScore = params.get('min_score')
  const source = params.get('source')
  const deadlineBefore = params.get('deadline_before')
  const role = params.get('role')
  const q = params.get('q')?.toLowerCase().trim()
  const sort = params.get('sort') ?? 'deadline'

  let items = db.jobs
    // Expired jobs that were never triaged are hidden.
    .filter((j) => !j.deadline || j.deadline >= today || j.status !== 'ny')
    .filter((j) => !type || j.job_type === type)
    .filter((j) => !status || j.status === status)
    .filter((j) => !minScore || (j.score ?? 0) >= Number(minScore))
    .filter((j) => !source || j.sources.includes(source as never))
    .filter((j) => !deadlineBefore || (j.deadline !== null && j.deadline <= deadlineBefore))
    .filter((j) => !role || j.role_category === role)
    .filter((j) => !q || `${j.title} ${j.company} ${j.location_text}`.toLowerCase().includes(q))
    .map(toListItem)

  if (sort === 'score') items = items.sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
  else if (sort === 'newest') items = items.sort((a, b) => (a.first_seen < b.first_seen ? 1 : -1))
  else items = items.sort(byDeadlineThenScore)
  return items
}

export function buildOverview(db: MockDb): S['Overview'] {
  const in14 = db.clock.day(14)
  const in7 = db.clock.day(7)
  const todayIso = db.clock.day(0)
  const live = (j: JobDetail) => !j.deadline || j.deadline >= todayIso

  const deadlines = db.jobs
    .filter((j) => (j.status === 'interessant' || j.status === 'utkast') && j.deadline && j.deadline >= todayIso && j.deadline <= in14)
    .map(toListItem)
    .sort(byDeadlineThenScore)

  const fresh = db.jobs.filter((j) => j.is_new && live(j))
  const counts: Partial<Record<JobType, number>> = {}
  for (const j of fresh) counts[j.job_type] = (counts[j.job_type] ?? 0) + 1

  const followUps = db.applications.cards.filter((a) => {
    if (CLOSED_STATUSES.includes(a.status)) return false
    const due = [a.follow_up_at, a.next_step_at].filter((d): d is string => !!d)
    return due.some((d) => d <= in7)
  })

  return {
    deadlines,
    new_since_last: {
      since: addDays(parseISO(db.lastRunAt), -1).toISOString(),
      counts_by_type: counts as S['NewSinceLast']['counts_by_type'],
      top: fresh.map(toListItem).sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 5),
    },
    follow_ups: followUps.map((a) => toCard(db, a)),
    sources: db.sources,
    cost: { month_usd: db.costMonthUsd, cap_usd: db.costCapUsd, warn: db.costMonthUsd >= db.costCapUsd * 0.8 },
    last_run_at: db.lastRunAt,
  }
}

const TRIAGE: readonly ApplicationStatus[] = ['ny', 'interessant', 'ikke_aktuell']

/**
 * Triage (FRONTEND §7): moves between ny, interessant and ikke_aktuell, creating or removing
 * the application row. Later statuses belong to the tracker, so they return null (→ 409).
 */
export function setTriageStatus(db: MockDb, job: JobDetail, status: S['JobStatusUpdate']['status']): S['JobStatusResult'] | null {
  if (!TRIAGE.includes(job.status)) return null
  const cards = db.applications.cards
  const now = new Date().toISOString()
  if (status === 'ny') {
    if (job.application) {
      db.applications.cards = cards.filter((a) => a.id !== job.application!.id)
      db.applications.events.delete(job.application.id)
    }
    job.application = null
  } else if (job.application) {
    const card = cards.find((a) => a.id === job.application!.id)!
    db.applications.events.get(card.id)!.push({ id: nextEventId(db), from_status: card.status, to_status: status, at: now, comment: null })
    card.status = status
    job.application.status = status
  } else {
    const id = Math.max(0, ...cards.map((a) => a.id)) + 1
    cards.push({
      id,
      job_id: job.id,
      status,
      job_title: job.title,
      company: job.company,
      deadline: job.deadline,
      applied_at: null,
      follow_up_at: null,
      next_step: null,
      next_step_at: null,
      contact_name: job.contacts[0]?.name ?? null,
      notes: null,
      created_at: now,
    })
    db.applications.events.set(id, [{ id: nextEventId(db), from_status: 'ny', to_status: status, at: now, comment: null }])
    job.application = { id, status, latest_draft_id: null }
  }
  job.status = status
  return { job_id: job.id, status, application_id: job.application?.id ?? null }
}

/** Legal status transitions (ARCHITECTURE §9.1). `utlopt` is set automatically, never by hand. */
export const TRANSITIONS: Record<ApplicationStatus, readonly ApplicationStatus[]> = {
  ny: ['interessant', 'ikke_aktuell'],
  interessant: ['utkast', 'sokt', 'ikke_aktuell'],
  utkast: ['sokt', 'ikke_aktuell'],
  sokt: ['intervju', 'avslag', 'trukket'],
  intervju: ['tilbud', 'avslag', 'trukket'],
  tilbud: ['trukket'],
  ikke_aktuell: ['interessant'],
  avslag: [],
  trukket: [],
  utlopt: [],
}

/** Status before the latest event; going back to it undoes that event. `ny` is triage's job. */
function previousStatus(db: MockDb, card: MockCard): ApplicationStatus | null {
  const from = db.applications.events.get(card.id)?.at(-1)?.from_status ?? null
  return from === 'ny' ? null : from
}

export function toCard(db: MockDb, card: MockCard): S['ApplicationCard'] {
  const latest = db.applications.drafts.filter((d) => d.application_id === card.id).at(-1)
  return {
    ...card,
    allowed_next: [...TRANSITIONS[card.status]],
    previous_status: previousStatus(db, card),
    latest_draft_id: latest?.id ?? null,
    latest_draft_at: latest?.created_at ?? null,
  }
}

const PATCH_FIELDS = ['next_step', 'next_step_at', 'follow_up_at', 'notes'] as const

/**
 * PATCH /api/applications/{id} (FRONTEND §7). Only fields present in the body change. A status
 * change must follow TRANSITIONS or go back to `previous_status` (undo: the event is removed).
 * Moving to `sokt` sets `applied_at` and, unless given, `follow_up_at` to +14 days.
 * Returns null on an illegal transition (→ 409).
 */
export function patchApplication(db: MockDb, card: MockCard, patch: S['ApplicationPatch']): MockCard | null {
  const to = patch.status
  if (to && to !== card.status) {
    const events = db.applications.events.get(card.id) ?? []
    if (to === previousStatus(db, card)) {
      events.pop()
      if (card.status === 'sokt') {
        card.applied_at = null
        if (!('follow_up_at' in patch)) card.follow_up_at = null
      }
    } else if (TRANSITIONS[card.status].includes(to)) {
      const now = new Date().toISOString()
      events.push({ id: nextEventId(db), from_status: card.status, to_status: to, at: now, comment: patch.comment ?? null })
      if (to === 'sokt') {
        card.applied_at = now
        if (!('follow_up_at' in patch)) card.follow_up_at = db.clock.day(14)
      }
    } else return null
    card.status = to
    const job = db.jobs.find((j) => j.id === card.job_id)
    if (job) {
      job.status = to
      if (job.application) job.application.status = to
    }
  }
  for (const k of PATCH_FIELDS) if (k in patch) card[k] = patch[k] ?? null
  return card
}

function nextEventId(db: MockDb) {
  return Math.max(0, ...[...db.applications.events.values()].flat().map((e) => e.id)) + 1
}

const isActive = (t: Task) => t.status === 'queued' || t.status === 'running'

/** How a mock task progresses and what it does when it finishes. */
export type TaskSpec = {
  ms: number
  steps: string[]
  finish: (at: string) => { message: string; result: Task['result'] }
}

const RUN_STEPS = ['Henter fra Finn', 'Henter fra NAV', 'Henter fra Teamtailor', 'Sjekker karrieresider', 'Filtrerer og scorer']

export function runSpec(db: MockDb): TaskSpec {
  return {
    ms: db.runMs,
    steps: RUN_STEPS,
    finish: (at) => {
      db.lastRunAt = at
      for (const s of db.sources) {
        if (s.source === 'manual') continue
        s.last_run_at = at
        s.new = 0
      }
      return { message: 'Ferdig: ingen nye jobber', result: null }
    },
  }
}

export function startTask(db: MockDb, kind: Task['kind'], spec: TaskSpec): S['TaskRef'] {
  const task: Task = {
    id: `mock-${kind}-${db.tasks.length + 1}`,
    kind,
    status: 'queued',
    progress: 0,
    message: 'I kø',
    created_at: new Date().toISOString(),
    finished_at: null,
    result: null,
  }
  db.tasks.push(task)
  db.taskSpecs.set(task.id, spec)
  return { task_id: task.id }
}

/** Advances a mock task from the wall clock, so polling sees progress without timers. */
export function tick(db: MockDb, task: Task, now = Date.now()): Task {
  if (!isActive(task)) return task
  const spec = db.taskSpecs.get(task.id)!
  const p = Math.min(1, (now - Date.parse(task.created_at)) / spec.ms)
  if (p < 1) {
    task.status = 'running'
    task.progress = Math.round(p * 100) / 100
    task.message = spec.steps[Math.min(spec.steps.length - 1, Math.floor(p * spec.steps.length))]!
    return task
  }
  const at = new Date(now).toISOString()
  const { message, result } = spec.finish(at)
  task.status = 'done'
  task.progress = 1
  task.message = message
  task.result = result
  task.finished_at = at
  return task
}

export function createHandlers(db: MockDb = createMockDb()) {
  return [
    http.get('/api/health', () => json<S['HealthStatus']>({ status: 'ok', version: 'mock' })),

    http.get('/api/overview', () => json<S['Overview']>(buildOverview(db))),

    http.get('/api/llm/usage', () => json<S['LlmUsage']>(buildLlmUsage(db.clock, db.llmState))),

    http.get('/api/jobs', ({ request }) => {
      const params = new URL(request.url).searchParams
      const all = filterJobs(db, params)
      const limit = Number(params.get('limit') ?? 50)
      const start = Number(params.get('cursor') ?? 0)
      const items = all.slice(start, start + limit)
      const next = start + limit < all.length ? String(start + limit) : null
      return json<S['JobList']>({ items, next_cursor: next, total: all.length })
    }),

    http.get('/api/jobs/:id', ({ params }) => {
      const job = db.jobs.find((j) => j.id === Number(params.id))
      return job ? json<S['JobDetail']>(job) : error(404, 'not_found', 'Fant ikke jobben.')
    }),

    http.get('/api/applications', ({ request }) => {
      const status = new URL(request.url).searchParams.get('status')
      const items = db.applications.cards.filter((a) => !status || a.status === status).map((a) => toCard(db, a))
      return json<S['ApplicationList']>({ items })
    }),

    http.patch('/api/applications/:id', async ({ params, request }) => {
      const card = db.applications.cards.find((a) => a.id === Number(params.id))
      if (!card) return error(404, 'not_found', 'Fant ikke søknaden.')
      const patch = (await request.json()) as S['ApplicationPatch']
      const from = card.status
      const result = patchApplication(db, card, patch)
      return result
        ? json<S['ApplicationCard']>(toCard(db, result))
        : error(409, 'invalid_transition', `Kan ikke gå fra ${from} til ${patch.status}.`)
    }),

    http.get('/api/applications/:id/events', ({ params }) =>
      json<S['ApplicationEvent'][]>(db.applications.events.get(Number(params.id)) ?? []),
    ),

    http.get('/api/applications/:id/drafts', ({ params }) =>
      json<S['DraftSummary'][]>(
        db.applications.drafts
          .filter((d) => d.application_id === Number(params.id))
          .map(({ content: _c, claims_to_verify: _v, ...summary }) => summary),
      ),
    ),

    http.get('/api/applications/:id/messages', ({ params }) =>
      json<S['DraftMessage'][]>(db.applications.messages.filter((m) => m.application_id === Number(params.id))),
    ),

    http.post('/api/applications/:id/messages/:messageId/style-rule', ({ params }) => {
      const msg = db.applications.messages.find(
        (m) => m.id === Number(params.messageId) && m.application_id === Number(params.id),
      )
      if (!msg) return error(404, 'not_found', 'Fant ikke meldingen.')
      if (!msg.style_rule) return error(409, 'no_style_rule', 'Meldingen har ingen foreslått stilregel.')
      msg.style_rule_saved = true
      return json<S['DraftMessage']>(msg)
    }),

    http.get('/api/drafts/:id', ({ params }) => {
      const draft = db.applications.drafts.find((d) => d.id === Number(params.id))
      return draft ? json<S['Draft']>(draft) : error(404, 'not_found', 'Fant ikke utkastet.')
    }),

    http.get('/api/drafts/:id/docx', ({ params }) => {
      const draft = db.applications.drafts.find((d) => d.id === Number(params.id))
      if (!draft) return error(404, 'not_found', 'Fant ikke utkastet.')
      const card = db.applications.cards.find((a) => a.id === draft.application_id)
      const name = `Søknad ${card?.company ?? ''} v${draft.version}.docx`.replace(/\s+/g, ' ')
      return new HttpResponse(markdownToDocx(draft.content), {
        headers: {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(name)}`,
        },
      })
    }),

    http.post('/api/jobs/:id/draft', ({ params }) => {
      const job = db.jobs.find((j) => j.id === Number(params.id))
      if (!job) return error(404, 'not_found', 'Fant ikke jobben.')
      const ref = startDraft(db, job)
      return ref ? json<S['TaskRef']>(ref, { status: 202 }) : error(409, 'draft_exists', 'Søknaden har allerede et utkast.')
    }),

    http.post('/api/applications/:id/drafts', async ({ params, request }) => {
      const id = Number(params.id)
      if (!db.applications.cards.some((a) => a.id === id)) return error(404, 'not_found', 'Fant ikke søknaden.')
      const draft = saveUserDraft(db, id, (await request.json()) as S['DraftCreate'])
      return draft ? json<S['Draft']>(draft, { status: 201 }) : error(404, 'not_found', 'Fant ikke versjonen.')
    }),

    http.post('/api/applications/:id/revise', async ({ params, request }) => {
      const id = Number(params.id)
      if (!db.applications.cards.some((a) => a.id === id)) return error(404, 'not_found', 'Fant ikke søknaden.')
      const ref = startRevise(db, id, (await request.json()) as S['ReviseRequest'])
      return ref ? json<S['TaskRef']>(ref, { status: 202 }) : error(409, 'no_draft', 'Søknaden har ikke noe utkast ennå.')
    }),

    http.put('/api/jobs/:id/status', async ({ params, request }) => {
      const job = db.jobs.find((j) => j.id === Number(params.id))
      if (!job) return error(404, 'not_found', 'Fant ikke jobben.')
      const { status } = (await request.json()) as S['JobStatusUpdate']
      const result = setTriageStatus(db, job, status)
      return result ? json<S['JobStatusResult']>(result) : error(409, 'invalid_transition', `Kan ikke gå fra ${job.status} til ${status} her.`)
    }),

    http.post('/api/runs', () => {
      if (db.tasks.some((t) => t.kind === 'run' && isActive(tick(db, t))))
        return error(409, 'run_active', 'En kjøring pågår allerede.')
      return json<S['TaskRef']>(startTask(db, 'run', runSpec(db)), { status: 202 })
    }),

    http.get('/api/tasks', ({ request }) => {
      const active = new URL(request.url).searchParams.get('active') === 'true'
      const tasks = db.tasks.map((t) => tick(db, t))
      return json<S['Task'][]>(active ? tasks.filter(isActive) : tasks)
    }),

    http.get('/api/tasks/:id', ({ params }) => {
      const task = db.tasks.find((t) => t.id === params.id)
      return task ? json<S['Task']>(tick(db, task)) : error(404, 'not_found', 'Fant ikke jobben.')
    }),

    http.post('/api/tasks/:id/cancel', ({ params }) => {
      const task = db.tasks.find((t) => t.id === params.id)
      if (!task) return error(404, 'not_found', 'Fant ikke jobben.')
      if (isActive(tick(db, task))) {
        task.status = 'cancelled'
        task.message = 'Avbrutt'
        task.finished_at = new Date().toISOString()
      }
      return json<S['Task']>(task)
    }),

    http.get('/api/profile/files', () =>
      json<S['ProfileTree']>({
        files: db.profileFiles.map(({ path, content, updated_at }) => ({ path, size: content.length, updated_at })),
        profile_hash: 'mockhash',
        derived_outdated: true,
      }),
    ),

    http.get('/api/profile/files/*', ({ request }) => {
      const path = decodeURIComponent(new URL(request.url).pathname.replace('/api/profile/files/', ''))
      if (path.endsWith('/revisions')) return json<S['ProfileRevision'][]>([])
      const file = db.profileFiles.find((f) => f.path === path)
      return file ? json<S['ProfileFile']>(file) : error(404, 'not_found', 'Fant ikke filen.')
    }),

    http.get('/api/settings', () => json<S['Settings']>({ items: db.settings })),

    http.get('/api/logs/runs', () => json<S['RunLog']>({ items: db.runs })),
    http.get('/api/logs/agent-runs', () => json<S['AgentRunLog']>({ items: db.agentRuns })),
    http.get('/api/logs/discarded', () => json<S['DiscardedLog']>({ items: db.discarded })),

    // Contract routes not mocked yet (mutations come in F4).
    http.all('/api/*', () => error(501, 'not_implemented', 'Ikke implementert i mock ennå.')),
  ]
}
