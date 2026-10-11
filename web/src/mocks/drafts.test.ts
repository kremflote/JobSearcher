import { createMockDb } from './db'
import { zip } from './docx'
import { startDraft, saveUserDraft, startRevise, USER_VERSION_WINDOW_MS } from './drafts'
import { isQuestion, reviseText } from './fixtures/drafts'
import { tick, toCard } from './handlers'

const fresh = () => createMockDb(new Date(2026, 9, 10, 12))

/** Runs a mock task to completion. */
function finish(db: ReturnType<typeof fresh>, taskId: string) {
  const task = db.tasks.find((t) => t.id === taskId)!
  return tick(db, task, Date.parse(task.created_at) + 60_000)
}

describe('mock drafts (FRONTEND §5.5)', () => {
  it('drafting an untriaged job creates the application in utkast with version 1', () => {
    const db = fresh()
    const job = db.jobs.find((j) => j.status === 'ny')!
    const ref = startDraft(db, job)!
    expect(job.application).toBeNull() // nothing happens until the task finishes

    const task = finish(db, ref.task_id)
    expect(task).toMatchObject({ status: 'done', message: 'Ferdig: versjon 1' })
    const card = db.applications.cards.find((a) => a.id === task.result!.application_id)!
    expect(card.status).toBe('utkast')
    expect(job.status).toBe('utkast')
    expect(job.application?.latest_draft_id).toBe(task.result!.draft_id)
    expect(toCard(db, card).latest_draft_id).toBe(task.result!.draft_id)
    expect(db.applications.events.get(card.id)!.map((e) => e.to_status)).toEqual(['interessant', 'utkast'])
    expect(startDraft(db, job)).toBeNull() // already has a draft → 409
  })

  it('autosave updates a recent user version in place, otherwise adds one', () => {
    const db = fresh()
    const appId = db.applications.drafts[0]!.application_id
    const count = () => db.applications.drafts.filter((d) => d.application_id === appId).length
    const before = count()

    const a = saveUserDraft(db, appId, { content: 'første' })!
    expect(a).toMatchObject({ author: 'user', content: 'første' })
    expect(count()).toBe(before + 1)
    const b = saveUserDraft(db, appId, { content: 'andre' })!
    expect(b.id).toBe(a.id)
    expect(count()).toBe(before + 1)

    a.created_at = new Date(Date.now() - USER_VERSION_WINDOW_MS - 1000).toISOString()
    const c = saveUserDraft(db, appId, { content: 'tredje' })!
    expect(c.version).toBe(a.version + 1)
    expect(saveUserDraft(db, appId, { content: 'x', base_draft_id: 9999 })).toBeNull()
  })

  it('user versions inherit claims from their base version', () => {
    const db = fresh()
    const v1 = db.applications.drafts.find((d) => d.version === 1 && d.claims_to_verify.length === 2)!
    const draft = saveUserDraft(db, v1.application_id, { content: 'x', base_draft_id: v1.id })!
    expect(draft.claims_to_verify).toEqual(v1.claims_to_verify)
  })

  it('revise adds an agent version with the instruction and a change summary', () => {
    const db = fresh()
    const appId = db.applications.drafts[0]!.application_id
    const task = finish(db, startRevise(db, appId, { instruction: 'Gjør det kortere' })!.task_id)
    const draft = db.applications.drafts.find((d) => d.id === task.result!.draft_id)!
    expect(draft).toMatchObject({ author: 'agent', instruction: 'Gjør det kortere' })
    expect(draft.change_summary).toMatch(/^Kuttet/)
    expect(startRevise(db, 99999, { instruction: 'x' })).toBeNull()
  })

  it('a question gets an answer in the chat and no new version', () => {
    const db = fresh()
    const appId = db.applications.drafts[0]!.application_id
    const versions = () => db.applications.drafts.filter((d) => d.application_id === appId).length
    const messages = () => db.applications.messages.filter((m) => m.application_id === appId)
    const before = versions()
    const ref = startRevise(db, appId, { instruction: 'Hvorfor skriver du at jeg ledet backend-arbeidet?' })!
    expect(messages().at(-1)).toMatchObject({ role: 'user', draft_id: null }) // stored at once
    const task = finish(db, ref.task_id)
    expect(task.result).toEqual({ application_id: appId, draft_id: null })
    expect(versions()).toBe(before)
    expect(messages().at(-1)).toMatchObject({ role: 'agent', draft_id: null })
  })

  it('a revision is answered by an agent message linked to the new version', () => {
    const db = fresh()
    const appId = db.applications.drafts[0]!.application_id
    const task = finish(db, startRevise(db, appId, { instruction: 'Mer formell tone' })!.task_id)
    expect(db.applications.messages.at(-1)).toMatchObject({ role: 'agent', draft_id: task.result!.draft_id })
    expect(db.applications.messages.at(-1)!.style_rule).toBeNull()
  })

  it('a general preference gets a suggested style rule', () => {
    const db = fresh()
    const appId = db.applications.drafts[0]!.application_id
    finish(db, startRevise(db, appId, { instruction: 'aldri bruk «brenner for»' })!.task_id)
    expect(db.applications.messages.at(-1)).toMatchObject({
      role: 'agent',
      style_rule: 'Aldri bruk «brenner for»',
      style_rule_saved: false,
    })
  })

  it('reviseText shortens on "kortere" and adds a sentence otherwise', () => {
    const text = 'Hei.\n\nEn. To. Tre.\n\nHilsen'
    expect(reviseText(text, 'kortere').content).toBe('Hei.\n\nEn. To.\n\nHilsen')
    expect(reviseText(text, 'mer formell').content).toContain('«mer formell»')
  })
})

describe('mock docx', () => {
  it('writes a valid stored zip', () => {
    const bytes = zip({ 'a.txt': 'hei' })
    const view = new DataView(bytes.buffer)
    expect(view.getUint32(0, true)).toBe(0x04034b50)
    expect(view.getUint32(bytes.length - 22, true)).toBe(0x06054b50)
    expect(view.getUint16(bytes.length - 12, true)).toBe(1) // one entry
  })
})

describe('isQuestion', () => {
  it('spots questions by "?" or a question word first', () => {
    expect(isQuestion('Kommer dette fra profilen')).toBe(true)
    expect(isQuestion('Er åpningen for lang?')).toBe(true)
    expect(isQuestion('Erstatt første setning')).toBe(false)
    expect(isQuestion('Gjør den kortere')).toBe(false)
  })
})
