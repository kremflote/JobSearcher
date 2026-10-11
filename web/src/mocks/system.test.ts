import { describe, expect, it } from 'vitest'
import { parseNumber, splitWords } from '@/features/settings/fields'
import { slugify } from '@/features/profile/paths'
import { createMockDb } from './db'
import { checkPath, mockHash, patchSettings, writeProfileFile } from './system'

describe('profile files (mock follows the API rules)', () => {
  it('keeps the original as the first revision and refuses a stale hash', () => {
    const db = createMockDb(new Date('2026-10-11T10:00:00Z'))
    const cv = db.profileFiles.find((f) => f.path === 'cv.md')!
    const original = cv.content
    const saved = writeProfileFile(db, 'cv.md', { content: original + 'Ny\n', base_hash: cv.content_hash })
    expect('code' in saved).toBe(false)
    const revs = db.profileRevisions.get('cv.md')!
    expect(revs.map((r) => r.content)).toEqual([original + 'Ny\n', original])
    expect(new Set(revs.map((r) => r.id)).size).toBe(2)
    expect(writeProfileFile(db, 'cv.md', { content: 'x', base_hash: mockHash(original) })).toMatchObject({ code: 'conflict' })
  })

  it('validates paths, YAML and creation', () => {
    const db = createMockDb()
    for (const p of ['../x.md', '.obsidian/a.md', 'cv.exe', 'projects/_template.md']) expect(checkPath(p)).not.toBeNull()
    expect(checkPath('projects/_template.md', { template: true })).toBeNull()
    const yaml = db.profileFiles.find((f) => f.path === 'profile.yaml')!
    expect(writeProfileFile(db, 'profile.yaml', { content: 'a: [b\n', base_hash: yaml.content_hash })).toMatchObject({ code: 'invalid_yaml' })
    expect(writeProfileFile(db, 'cv.md', { content: 'x', base_hash: null })).toMatchObject({ code: 'file_exists' })
  })
})

describe('settings (mock)', () => {
  it('overrides, removes the override at the default, and checks ranges', () => {
    const db = createMockDb()
    const item = () => db.settings.find((s) => s.key === 'llm.warn_ratio')!
    patchSettings(db, { 'llm.warn_ratio': 0.9 })
    expect(item()).toMatchObject({ value: 0.9, overridden: true })
    patchSettings(db, { 'llm.warn_ratio': 0.8 })
    expect(item()).toMatchObject({ value: 0.8, overridden: false })
    expect(patchSettings(db, { 'llm.warn_ratio': 2 })).toMatchObject({ code: 'invalid_setting' })
    expect(patchSettings(db, { 'search.repost_after_days': 3 })).toMatchObject({ code: 'unknown_setting' })
  })
})

describe('helpers', () => {
  it('parses Norwegian numbers', () => {
    expect(parseNumber('0,8', 'number')).toBe(0.8)
    expect(parseNumber('1.5', 'int')).toBeNull()
    expect(parseNumber('abc', 'number')).toBeNull()
  })
  it('splits word lists', () => expect(splitWords(' hr, salg\nlager ,')).toEqual(['hr', 'salg', 'lager']))
  it('slugifies file names', () => expect(slugify('Værapp for Blåbærturer.md')).toBe('vaerapp-for-blabaerturer'))
})
