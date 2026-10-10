import { activeFilterCount, filtersToParams, parseFilters, toApiQuery } from './filters'

describe('job filters in the URL', () => {
  it('defaults to new jobs sorted by deadline', () => {
    const f = parseFilters(new URLSearchParams())
    expect(f).toMatchObject({ type: null, status: 'ny', sort: 'deadline', q: '' })
    expect(filtersToParams(f).toString()).toBe('')
    expect(activeFilterCount(f)).toBe(0)
  })

  it('round-trips and drops invalid values', () => {
    const f = parseFilters(new URLSearchParams('type=trainee&min_score=60&status=alle&source=bogus&deadline_before=2026-11-01&sort=score'))
    expect(f).toMatchObject({ type: 'trainee', min_score: 60, status: 'alle', source: null, deadline_before: '2026-11-01', sort: 'score' })
    expect(parseFilters(filtersToParams(f))).toEqual(f)
    expect(activeFilterCount(f)).toBe(3)
  })

  it('sends "alle" as no status filter', () => {
    expect(toApiQuery(parseFilters(new URLSearchParams('status=alle'))).status).toBeUndefined()
    expect(toApiQuery(parseFilters(new URLSearchParams('q=%20%20'))).q).toBeUndefined()
  })
})
