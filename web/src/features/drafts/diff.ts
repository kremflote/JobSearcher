export type DiffPart = { kind: 'same' | 'added' | 'removed'; text: string }

/** Words and the whitespace after them, so joining the tokens gives the text back. */
const tokenize = (text: string) => text.match(/\s+|[^\s]+\s*/g) ?? []

/**
 * Word diff from `before` to `after` (FRONTEND §5.5 version picker). Plain LCS: cover letters are
 * a few hundred words, so O(n·m) is fine. Neighbouring parts of the same kind are merged.
 */
export function diffWords(before: string, after: string): DiffPart[] {
  const a = tokenize(before)
  const b = tokenize(after)
  const n = a.length
  const m = b.length
  // lcs[i][j] = LCS length of a[i:] and b[j:], compared without trailing whitespace.
  const key = (s: string) => s.trimEnd()
  const lcs = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1))
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      lcs[i]![j] = key(a[i]!) === key(b[j]!) ? lcs[i + 1]![j + 1]! + 1 : Math.max(lcs[i + 1]![j]!, lcs[i]![j + 1]!)

  const parts: DiffPart[] = []
  const push = (kind: DiffPart['kind'], text: string) => {
    const last = parts.at(-1)
    if (last?.kind === kind) last.text += text
    else parts.push({ kind, text })
  }
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (key(a[i]!) === key(b[j]!)) {
      push('same', b[j]!)
      i++
      j++
    } else if (lcs[i + 1]![j]! >= lcs[i]![j + 1]!) push('removed', a[i++]!)
    else push('added', b[j++]!)
  }
  while (i < n) push('removed', a[i++]!)
  while (j < m) push('added', b[j++]!)
  return parts
}

/** Words added and removed, for the version list. */
export function diffStats(parts: DiffPart[]) {
  const words = (s: string) => s.split(/\s+/).filter(Boolean).length
  return {
    added: parts.filter((p) => p.kind === 'added').reduce((n, p) => n + words(p.text), 0),
    removed: parts.filter((p) => p.kind === 'removed').reduce((n, p) => n + words(p.text), 0),
  }
}

export const wordCount = (text: string) => text.split(/\s+/).filter(Boolean).length
