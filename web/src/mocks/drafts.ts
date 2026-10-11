/**
 * Mock writer and reviser agents (FRONTEND §5.5, F3). The text is a template, the "revision" a
 * visible, predictable edit, and a question gets a canned answer without a new version, so the
 * editor flow can be tested before backend phase 3.
 */
import type { components } from '@/api/schema'
import type { Draft, DraftMessage, JobDetail } from '@/api/types'
import type { MockDb } from './db'
import { DRAFT_CLAIMS, draftText, isQuestion, MOCK_ANSWER, reviseText, styleRule } from './fixtures/drafts'
import { patchApplication, setTriageStatus, startTask } from './handlers'

type S = components['schemas']

/** A user version is updated in place within this window instead of adding a version (DraftCreate). */
export const USER_VERSION_WINDOW_MS = 10 * 60_000

const draftsOf = (db: MockDb, applicationId: number) => db.applications.drafts.filter((d) => d.application_id === applicationId)

function addDraft(db: MockDb, fields: Omit<Draft, 'id' | 'version' | 'created_at'>): Draft {
  const draft: Draft = {
    ...fields,
    id: Math.max(0, ...db.applications.drafts.map((d) => d.id)) + 1,
    version: Math.max(0, ...draftsOf(db, fields.application_id).map((d) => d.version)) + 1,
    created_at: new Date().toISOString(),
  }
  db.applications.drafts.push(draft)
  const job = db.jobs.find((j) => j.application?.id === fields.application_id)
  if (job?.application) job.application.latest_draft_id = draft.id
  return draft
}

function addMessage(
  db: MockDb,
  applicationId: number,
  role: DraftMessage['role'],
  text: string,
  draftId: number | null = null,
  styleRule: string | null = null,
) {
  const message: DraftMessage = {
    id: Math.max(0, ...db.applications.messages.map((m) => m.id)) + 1,
    application_id: applicationId,
    role,
    text,
    draft_id: draftId,
    style_rule: styleRule,
    style_rule_saved: false,
    created_at: new Date().toISOString(),
  }
  db.applications.messages.push(message)
  return message
}

/**
 * POST /api/jobs/{id}/draft: research + writer as a background task. Creates the application if
 * the job is untriaged and moves it to `utkast` (ARCHITECTURE §9.1). Returns null when the job
 * already has drafts (→ 409 `draft_exists`).
 */
export function startDraft(db: MockDb, job: JobDetail): S['TaskRef'] | null {
  if (job.application?.latest_draft_id) return null
  return startTask(db, 'draft', {
    ms: db.draftMs,
    steps: [`Researcher ${job.company}`, 'Skriver utkast', 'Sjekker påstander'],
    finish: () => {
      if (!job.application) setTriageStatus(db, job, 'interessant')
      const card = db.applications.cards.find((a) => a.id === job.application!.id)!
      if (card.status === 'interessant') patchApplication(db, card, { status: 'utkast' })
      const draft = addDraft(db, {
        application_id: card.id,
        author: 'agent',
        instruction: null,
        change_summary: 'Første utkast.',
        content: draftText(job),
        claims_to_verify: [...DRAFT_CLAIMS],
      })
      addMessage(db, card.id, 'agent', 'Første utkast.', draft.id)
      return { message: 'Ferdig: versjon 1', result: { application_id: card.id, draft_id: draft.id } }
    },
  })
}

/** POST /api/applications/{id}/drafts (autosave). Returns null when the base version is unknown. */
export function saveUserDraft(db: MockDb, applicationId: number, body: S['DraftCreate']): Draft | null {
  const drafts = draftsOf(db, applicationId)
  const latest = drafts.at(-1)
  const base = body.base_draft_id ? drafts.find((d) => d.id === body.base_draft_id) : latest
  if (body.base_draft_id && !base) return null
  if (latest?.author === 'user' && Date.now() - Date.parse(latest.created_at) < USER_VERSION_WINDOW_MS) {
    latest.content = body.content
    return latest
  }
  return addDraft(db, {
    application_id: applicationId,
    author: 'user',
    instruction: null,
    change_summary: null,
    content: body.content,
    claims_to_verify: [...(base?.claims_to_verify ?? [])],
  })
}

/**
 * POST /api/applications/{id}/revise: the message is stored at once; the task then either answers
 * (a question, no new version) or revises. Returns null when there is no version to revise.
 */
export function startRevise(db: MockDb, applicationId: number, body: S['ReviseRequest']): S['TaskRef'] | null {
  const drafts = draftsOf(db, applicationId)
  const base = body.draft_id ? drafts.find((d) => d.id === body.draft_id) : drafts.at(-1)
  if (!base) return null
  addMessage(db, applicationId, 'user', body.instruction)
  if (isQuestion(body.instruction))
    return startTask(db, 'revise', {
      ms: db.reviseMs,
      steps: ['Leser utkastet', 'Svarer'],
      finish: () => {
        addMessage(db, applicationId, 'agent', MOCK_ANSWER)
        return { message: 'Ferdig: svar i chatten', result: { application_id: applicationId, draft_id: null } }
      },
    })
  return startTask(db, 'revise', {
    ms: db.reviseMs,
    steps: ['Leser utkastet', 'Skriver ny versjon'],
    finish: () => {
      const { content, summary } = reviseText(base.content, body.instruction)
      const draft = addDraft(db, {
        application_id: applicationId,
        author: 'agent',
        instruction: body.instruction,
        change_summary: summary,
        content,
        claims_to_verify: base.claims_to_verify.slice(0, 1),
      })
      addMessage(db, applicationId, 'agent', summary, draft.id, styleRule(body.instruction))
      return { message: `Ferdig: versjon ${draft.version}`, result: { application_id: applicationId, draft_id: draft.id } }
    },
  })
}

/**
 * DELETE /api/applications/{id}/drafts, and part of a move to `ikke_aktuell`: drops versions and
 * chat; `utkast` goes back to `interessant` by removing the event that moved it there.
 */
export function discardDrafts(db: MockDb, applicationId: number) {
  db.applications.drafts = db.applications.drafts.filter((d) => d.application_id !== applicationId)
  db.applications.messages = db.applications.messages.filter((m) => m.application_id !== applicationId)
  const card = db.applications.cards.find((a) => a.id === applicationId)
  const job = db.jobs.find((j) => j.application?.id === applicationId)
  if (job?.application) job.application.latest_draft_id = null
  if (card?.status !== 'utkast') return
  const events = db.applications.events.get(applicationId) ?? []
  if (events.at(-1)?.to_status === 'utkast') events.pop()
  card.status = 'interessant'
  if (job) {
    job.status = 'interessant'
    if (job.application) job.application.status = 'interessant'
  }
}
