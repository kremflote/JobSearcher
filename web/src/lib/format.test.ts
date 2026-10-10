import { deadlineInfo, scoreTone } from './format'

const today = new Date(2026, 9, 10, 12)

describe('scoreTone', () => {
  it.each([
    [100, 'good'],
    [70, 'good'],
    [69, 'neutral'],
    [50, 'neutral'],
    [49, 'muted'],
  ] as const)('%i → %s', (score, tone) => {
    expect(scoreTone(score)).toBe(tone)
  })
})

describe('deadlineInfo', () => {
  it.each([
    ['2026-10-09', 'utløpt', 'muted'],
    ['2026-10-10', 'i dag', 'bad'],
    ['2026-10-11', 'i morgen', 'bad'],
    ['2026-10-13', 'om 3 d', 'bad'],
    ['2026-10-14', 'om 4 d', 'warn'],
    ['2026-10-17', 'om 7 d', 'warn'],
    ['2026-10-18', 'om 8 d', 'neutral'],
  ] as const)('%s → %s (%s)', (deadline, relative, tone) => {
    const info = deadlineInfo(deadline, null, today)
    expect(info.relative).toBe(relative)
    expect(info.tone).toBe(tone)
  })

  it('formats the date in Norwegian', () => {
    expect(deadlineInfo('2026-10-14', null, today).date).toBe('14. okt. 2026')
  })

  it('falls back to deadline text, then a dash', () => {
    expect(deadlineInfo(null, 'snarest', today)).toMatchObject({ relative: 'snarest', date: null, days: null })
    expect(deadlineInfo(null, null, today).relative).toBe('—')
  })
})
