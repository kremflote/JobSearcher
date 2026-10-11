import type { ApplicationCard, ApplicationEvent, ApplicationStatus, Draft, DraftMessage, JobDetail } from '@/api/types'
import { DRAFT_CLAIMS, draftText, reviseText } from './drafts'
import type { Clock } from './time'

/** Status path from `ny` to each status, following ARCHITECTURE §9.1. */
const PATH: Record<ApplicationStatus, ApplicationStatus[]> = {
  ny: [],
  interessant: ['interessant'],
  utkast: ['interessant', 'utkast'],
  sokt: ['interessant', 'utkast', 'sokt'],
  intervju: ['interessant', 'utkast', 'sokt', 'intervju'],
  tilbud: ['interessant', 'utkast', 'sokt', 'intervju', 'tilbud'],
  ikke_aktuell: ['ikke_aktuell'],
  avslag: ['interessant', 'utkast', 'sokt', 'avslag'],
  trukket: ['interessant', 'utkast', 'sokt', 'trukket'],
  utlopt: ['interessant', 'utlopt'],
}

const NEXT_STEP: Partial<Record<ApplicationStatus, [string, number]>> = {
  intervju: ['Intervju 2. runde', 3],
  tilbud: ['Svar på tilbud', 5],
  utkast: ['Les over og send', 1],
}

/** Stored card; `allowed_next`, `previous_status` and the latest draft are derived when served (handlers.ts). */
export type MockCard = Omit<ApplicationCard, 'allowed_next' | 'previous_status' | 'latest_draft_id' | 'latest_draft_at'>

export type MockApplications = {
  cards: MockCard[]
  events: Map<number, ApplicationEvent[]>
  drafts: Draft[]
  messages: DraftMessage[]
}

export function buildApplications(jobs: JobDetail[], c: Clock): MockApplications {
  const cards: MockCard[] = []
  const events = new Map<number, ApplicationEvent[]>()
  const drafts: Draft[] = []
  const messages: DraftMessage[] = []
  const say = (application_id: number, role: DraftMessage['role'], text: string, draft_id: number | null, created_at: string) =>
    messages.push({
      id: messages.length + 1,
      application_id,
      role,
      text,
      draft_id,
      style_rule: null,
      style_rule_saved: false,
      created_at,
    })
  let eventId = 1
  let draftId = 1

  for (const job of jobs) {
    if (job.status === 'ny') continue
    const id = job.id - 1000 + 500
    const path = PATH[job.status]
    const started = -Math.max(1, Math.round((Date.now() - Date.parse(job.first_seen)) / 864e5) - 1)
    const step = Math.max(1, Math.floor(-started / (path.length + 1)))

    const evs: ApplicationEvent[] = []
    let from: ApplicationStatus | null = 'ny'
    path.forEach((to, k) => {
      evs.push({ id: eventId++, from_status: from, to_status: to, at: c.at(started + k * step, 9 + k), comment: null })
      from = to
    })
    events.set(id, evs)

    const appliedEvent = evs.find((e) => e.to_status === 'sokt')
    const appliedDay = appliedEvent ? started + path.indexOf('sokt') * step : null
    const next = NEXT_STEP[job.status]
    const contact = job.contacts[0]

    cards.push({
      id,
      job_id: job.id,
      status: job.status,
      job_title: job.title,
      company: job.company,
      deadline: job.deadline,
      applied_at: appliedEvent?.at ?? null,
      follow_up_at: job.status === 'sokt' && appliedDay !== null ? c.day(appliedDay + 14) : null,
      next_step: next?.[0] ?? null,
      next_step_at: next ? c.day(next[1]) : null,
      contact_name: contact?.name ?? null,
      notes: job.status === 'intervju' ? 'Første intervju gikk bra. Forbered case om API-design.' : null,
      created_at: evs[0]!.at,
    })

    if (path.includes('utkast')) {
      const versions = job.status === 'utkast' ? 3 : 2
      for (let v = 1; v <= versions; v++) {
        const agent = v !== 2
        const at = c.at(started + step, 10 + v)
        if (v === 3) say(id, 'user', 'Gjør andre avsnitt kortere og mer konkret.', null, at)
        if (agent) say(id, 'agent', v === 1 ? 'Første utkast.' : 'Strammet inn andre avsnitt.', draftId, at)
        drafts.push({
          id: draftId++,
          application_id: id,
          version: v,
          author: agent ? 'agent' : 'user',
          instruction: v === 3 ? 'Gjør andre avsnitt kortere og mer konkret.' : null,
          change_summary: v === 1 ? 'Første utkast.' : v === 2 ? null : 'Strammet inn andre avsnitt.',
          created_at: at,
          content: v === 3 ? reviseText(draftText(job), 'kortere').content : draftText(job),
          claims_to_verify: DRAFT_CLAIMS.slice(0, v === 1 ? 2 : 1),
        })
      }
    }

    const latest = drafts.filter((d) => d.application_id === id).at(-1)
    job.application = { id, status: job.status, latest_draft_id: latest?.id ?? null }
  }

  return { cards, events, drafts, messages }
}
