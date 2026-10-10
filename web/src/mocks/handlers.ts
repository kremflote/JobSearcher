/**
 * MSW handlers for the v0 contract (FRONTEND §7). F0 serves the read endpoints from the
 * fixtures; mutations are added per wave. Anything else under /api gets the contract's 501.
 */
import { addDays, parseISO } from 'date-fns'
import { http, HttpResponse } from 'msw'
import type { components } from '@/api/schema'
import type { ApplicationStatus, JobDetail, JobListItem, JobType } from '@/api/types'
import { CLOSED_STATUSES } from '@/lib/status'
import { createMockDb, toListItem, type MockDb } from './db'

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
    follow_ups: followUps,
    sources: db.sources,
    cost: { month_usd: db.costMonthUsd, cap_usd: db.costCapUsd, warn: db.costMonthUsd >= db.costCapUsd * 0.8 },
    last_run_at: db.lastRunAt,
  }
}

export function createHandlers(db: MockDb = createMockDb()) {
  return [
    http.get('/api/health', () => json<S['HealthStatus']>({ status: 'ok', version: 'mock' })),

    http.get('/api/overview', () => json<S['Overview']>(buildOverview(db))),

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
      const items = db.applications.cards.filter((a) => !status || a.status === status)
      return json<S['ApplicationList']>({ items })
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

    http.get('/api/drafts/:id', ({ params }) => {
      const draft = db.applications.drafts.find((d) => d.id === Number(params.id))
      return draft ? json<S['Draft']>(draft) : error(404, 'not_found', 'Fant ikke utkastet.')
    }),

    http.get('/api/tasks', () => json<S['Task'][]>(db.tasks.filter((t) => t.status === 'queued' || t.status === 'running'))),

    http.get('/api/tasks/:id', ({ params }) => {
      const task = db.tasks.find((t) => t.id === params.id)
      return task ? json<S['Task']>(task) : error(404, 'not_found', 'Fant ikke jobben.')
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

    // Contract routes not mocked yet (mutations come in F1–F4).
    http.all('/api/*', () => error(501, 'not_implemented', 'Ikke implementert i mock ennå.')),
  ]
}
