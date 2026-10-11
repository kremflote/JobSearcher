import type { SettingItem } from '@/api/types'

export type Section = SettingItem['section']

/** Section order and headings (FRONTEND §5.7). Kontekst and Utseende are added by the page. */
export const SECTIONS: { id: Section; title: string; intro?: string }[] = [
  { id: 'search', title: 'Søk', intro: 'Hva som samles inn og hva hardfilteret forkaster.' },
  { id: 'scoring', title: 'Scoring' },
  { id: 'notify', title: 'E-postdigest' },
  { id: 'llm', title: 'LLM' },
  { id: 'cost', title: 'Kostnad' },
  { id: 'schedule', title: 'Planlegging' },
  { id: 'sources', title: 'Kilder', intro: 'Kilder som er av, hoppes over i den daglige kjøringen.' },
]

/** Readable value for "Standard: …". */
export function formatValue(item: SettingItem, value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (item.kind === 'bool') return value ? 'på' : 'av'
  if (Array.isArray(value)) return value.length ? value.join(', ') : '(tom)'
  if (typeof value === 'number') return String(value).replace('.', ',')
  return String(value)
}

/** Parses the text in a number field ("0,8" or "0.8"). Null when it isn't a number. */
export function parseNumber(text: string, kind: 'int' | 'number'): number | null {
  const t = text.trim().replace(',', '.')
  if (!t || !/^-?\d+(\.\d+)?$/.test(t)) return null
  const n = Number(t)
  return kind === 'int' && !Number.isInteger(n) ? null : n
}

/** Splits pasted or typed words on commas and new lines. */
export const splitWords = (text: string) =>
  text
    .split(/[,\n]/)
    .map((w) => w.trim())
    .filter(Boolean)
