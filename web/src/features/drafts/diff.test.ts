import { diffStats, diffWords, wordCount } from './diff'

const join = (parts: ReturnType<typeof diffWords>, skip: 'added' | 'removed') =>
  parts.filter((p) => p.kind !== skip).map((p) => p.text).join('')

describe('diffWords', () => {
  it('rebuilds both texts', () => {
    const before = 'Jeg liker å jobbe tett med teamet.\n\nHilsen Ola'
    const after = 'Jeg liker godt å jobbe med teamet.\n\nHilsen Ola'
    const parts = diffWords(before, after)
    expect(join(parts, 'added')).toBe(before)
    expect(join(parts, 'removed')).toBe(after)
    expect(diffStats(parts)).toEqual({ added: 1, removed: 1 })
  })

  it('marks everything as same for equal texts', () => {
    expect(diffWords('a b c', 'a b c')).toEqual([{ kind: 'same', text: 'a b c' }])
  })

  it('handles empty texts', () => {
    expect(diffWords('', 'ny tekst')).toEqual([{ kind: 'added', text: 'ny tekst' }])
    expect(diffWords('gammel', '')).toEqual([{ kind: 'removed', text: 'gammel' }])
  })
})

describe('wordCount', () => {
  it('counts words across lines', () => {
    expect(wordCount(' Hei,\n\nJeg søker  her. ')).toBe(4)
    expect(wordCount('')).toBe(0)
  })
})
