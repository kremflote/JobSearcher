/**
 * Mock profile, settings and rescore (FRONTEND §5.6–5.7), following the rules of the real API:
 * profile saves check `base_hash` and keep the original as the first revision; YAML is checked
 * (crudely: unbalanced brackets or tab indentation); settings validate kind and range, and a
 * value equal to the default removes the override.
 */
import type { components } from '@/api/schema'
import type { ProfileFile, SettingItem } from '@/api/types'
import type { MockDb } from './db'
import { startTask, type TaskSpec } from './handlers'

type S = components['schemas']
export type MockError = { status: number; code: string; detail: string }

const SUFFIXES = ['.md', '.yaml', '.yml', '.txt']

/** Small stable string hash; the mock only needs it to change with the content. */
export function mockHash(text: string) {
  let h = 5381
  for (let i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) >>> 0
  return h.toString(16).padStart(8, '0')
}

export function checkPath(path: string, { template = false } = {}): MockError | null {
  const parts = path.split('/')
  const name = parts.at(-1) ?? ''
  const bad =
    !path ||
    path.startsWith('/') ||
    path.includes(':') ||
    parts.some((p) => !p || p === '.' || p === '..' || p.startsWith('.')) ||
    !SUFFIXES.some((s) => name.toLowerCase().endsWith(s))
  const underscore = parts.some((p) => p.startsWith('_'))
  if (bad || (underscore && !(template && name === '_template.md')))
    return { status: 400, code: 'invalid_path', detail: `Ugyldig filsti: ${path}` }
  return null
}

function yamlError(content: string): string | null {
  const lines = content.split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!
    const open = (line.match(/[[{]/g) ?? []).length
    const close = (line.match(/[\]}]/g) ?? []).length
    if (line.startsWith('\t') || open !== close) return `Ugyldig YAML (linje ${i + 1})`
  }
  return null
}

export function readTemplate(db: MockDb, path: string): ProfileFile | null {
  const folder = path.split('/').slice(0, -1).join('/')
  const content = db.profileTemplates.get(folder)
  return content === undefined ? null : { path, content, content_hash: mockHash(content), updated_at: db.clock.at(-30, 12) }
}

export function writeProfileFile(db: MockDb, path: string, body: S['ProfileFileWrite']): ProfileFile | MockError {
  const pathError = checkPath(path)
  if (pathError) return pathError
  const content = body.content.replace(/\r\n/g, '\n')
  if (/\.ya?ml$/i.test(path)) {
    const err = yamlError(content)
    if (err) return { status: 422, code: 'invalid_yaml', detail: err }
  }
  const existing = db.profileFiles.find((f) => f.path === path)
  if (!body.base_hash && existing) return { status: 409, code: 'file_exists', detail: 'Filen finnes allerede.' }
  if (body.base_hash) {
    if (!existing) return { status: 404, code: 'not_found', detail: 'Fant ikke filen.' }
    if (existing.content_hash !== body.base_hash)
      return { status: 409, code: 'conflict', detail: 'Filen er endret et annet sted. Last inn på nytt.' }
    if (existing.content === content) return existing
  }
  const now = new Date().toISOString()
  const revisions = db.profileRevisions.get(path) ?? []
  db.profileRevisions.set(path, revisions)
  const nextId = () => Math.max(0, ...[...db.profileRevisions.values()].flat().map((r) => r.id)) + 1
  if (existing && !revisions.length)
    revisions.unshift({ id: nextId(), path, content: existing.content, content_hash: existing.content_hash, created_at: existing.updated_at })
  const file: ProfileFile = { path, content, content_hash: mockHash(content), updated_at: now }
  revisions.unshift({ id: nextId(), path, content, content_hash: file.content_hash, created_at: now })
  if (existing) Object.assign(existing, file)
  else db.profileFiles.push(file)
  db.derivedOutdated = true
  return file
}

export function profileTree(db: MockDb): S['ProfileTree'] {
  return {
    files: [...db.profileFiles]
      .sort((a, b) => a.path.localeCompare(b.path))
      .map(({ path, content, updated_at }) => ({ path, size: new Blob([content]).size, updated_at })),
    folders: db.profileFolders,
    profile_hash: mockHash(db.profileFiles.map((f) => f.path + f.content_hash).join()),
    derived_outdated: db.derivedOutdated,
    derived_at: db.derived.made_at,
  }
}

export function distillSpec(db: MockDb): TaskSpec {
  return {
    ms: db.distillMs,
    steps: ['Leser profilen', 'Destillerer profilen', 'Skriver kortversjon og stemme'],
    finish: (at) => {
      db.derived = {
        made_at: at,
        model: db.derived.model,
        files: db.derived.files.map((f) => ({
          name: f.name,
          previous_content: f.content,
          content: `${f.content.trimEnd()}\n\n(Oppdatert ${at.slice(0, 10)}.)\n`,
        })),
      }
      db.derivedOutdated = false
      db.staleJobs = Math.max(db.staleJobs, 12)
      return { message: 'Ferdig: profilen er destillert', result: null }
    },
  }
}

export function rescoreSpec(db: MockDb): TaskSpec {
  const n = db.staleJobs
  return {
    ms: db.rescoreMs,
    steps: ['Scorer annonser'],
    finish: () => {
      db.staleJobs = 0
      return { message: `Ferdig: ${n} jobber scoret på nytt`, result: null }
    },
  }
}

export const MOCK_COST_PER_JOB = 0.0011

export function rescoreEstimate(db: MockDb): S['RescoreEstimate'] {
  return {
    stale_jobs: db.staleJobs,
    estimated_cost_usd: Math.round(db.staleJobs * MOCK_COST_PER_JOB * 10000) / 10000,
    cost_per_job_usd: MOCK_COST_PER_JOB,
  }
}

export function startMockTask(db: MockDb, kind: 'distill' | 'rescore'): S['TaskRef'] {
  return startTask(db, kind, kind === 'distill' ? distillSpec(db) : rescoreSpec(db))
}

const invalid = (item: SettingItem, why: string): MockError => ({
  status: 422,
  code: 'invalid_setting',
  detail: `${item.label}: ${why}`,
})

function coerce(item: SettingItem, value: unknown): unknown {
  switch (item.kind) {
    case 'bool':
      if (typeof value !== 'boolean') throw invalid(item, 'må være av eller på.')
      return value
    case 'int':
    case 'number': {
      if (typeof value !== 'number' || Number.isNaN(value)) throw invalid(item, 'må være et tall.')
      if (item.kind === 'int' && !Number.isInteger(value)) throw invalid(item, 'må være et heltall.')
      if ((item.min !== null && value < item.min) || (item.max !== null && value > item.max))
        throw invalid(item, `må være mellom ${String(item.min).replace('.', ',')} og ${String(item.max).replace('.', ',')}.`)
      return value
    }
    case 'string_list':
      if (!Array.isArray(value) || !value.every((v) => typeof v === 'string')) throw invalid(item, 'må være en liste med ord.')
      return [...new Set(value.map((v: string) => v.trim()).filter(Boolean))]
    default: {
      if (typeof value !== 'string' || !value.trim()) throw invalid(item, 'kan ikke være tom.')
      const v = value.trim()
      if (item.kind === 'time' && !/^([01]\d|2[0-3]):[0-5]\d$/.test(v)) throw invalid(item, 'må være et klokkeslett (TT:MM).')
      if (item.kind === 'enum' && !item.options?.includes(v)) throw invalid(item, `ukjent verdi «${v}».`)
      return v
    }
  }
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

/** PATCH /api/settings. All values are checked before any is applied. */
export function patchSettings(db: MockDb, values: Record<string, unknown>): SettingItem[] | MockError {
  const unknown = Object.keys(values).filter((k) => !db.settings.some((s) => s.key === k))
  if (unknown.length)
    return { status: 422, code: 'unknown_setting', detail: `Kan ikke endres i dashboardet: ${unknown.join(', ')}` }
  const next = new Map<string, unknown>()
  try {
    for (const [key, raw] of Object.entries(values)) {
      const item = db.settings.find((s) => s.key === key)!
      next.set(key, raw === null ? null : coerce(item, raw))
    }
  } catch (e) {
    return e as MockError
  }
  for (const [key, value] of next) {
    const item = db.settings.find((s) => s.key === key)!
    item.overridden = value !== null && !same(value, item.default)
    item.value = item.overridden ? value : item.default
  }
  return db.settings
}
