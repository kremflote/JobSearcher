/** Job list filters, stored in the URL so they can be bookmarked (FRONTEND §5.2). */
import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import type { JobQuery, TriageStatus } from '@/api/queries'
import type { JobListItem, JobType, SourceName } from '@/api/types'
import type { components } from '@/api/schema'

type RoleCategory = components['schemas']['Evaluation']['role_category']
type JobSort = NonNullable<JobQuery['sort']>

export type StatusFilter = TriageStatus | 'alle'

export type JobFilters = {
  type: JobType | null
  /** Default `ny`: the list is for triage. */
  status: StatusFilter
  min_score: number | null
  source: SourceName | null
  deadline_before: string | null
  role: RoleCategory | null
  q: string
  sort: JobSort
}

export const TYPE_TABS: { value: JobType | null; label: string }[] = [
  { value: null, label: 'Alle' },
  { value: 'permanent', label: 'Fast' },
  { value: 'trainee', label: 'Trainee' },
  { value: 'graduate', label: 'Graduate' },
  { value: 'summer', label: 'Sommerjobb' },
]

export const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'ny', label: 'Ikke vurdert' },
  { value: 'interessant', label: 'Interessant' },
  { value: 'ikke_aktuell', label: 'Ikke aktuell' },
  { value: 'alle', label: 'Alle' },
]

export const SORT_OPTIONS: { value: JobSort; label: string }[] = [
  { value: 'deadline', label: 'Frist' },
  { value: 'score', label: 'Score' },
  { value: 'newest', label: 'Nyeste' },
]

export const SOURCE_OPTIONS: { value: SourceName; label: string }[] = [
  { value: 'finn_api', label: 'Finn' },
  { value: 'nav', label: 'NAV' },
  { value: 'teamtailor', label: 'Teamtailor' },
  { value: 'page_watch', label: 'Karrieresider' },
  { value: 'manual', label: 'Manuell' },
]

export const ROLE_OPTIONS: { value: RoleCategory; label: string }[] = [
  { value: 'backend', label: 'Backend' },
  { value: 'frontend', label: 'Frontend' },
  { value: 'fullstack', label: 'Fullstack' },
  { value: 'mobile', label: 'Mobil' },
  { value: 'devops', label: 'DevOps' },
  { value: 'data', label: 'Data' },
  { value: 'other', label: 'Annet' },
]

export const MIN_SCORE_OPTIONS = [50, 60, 70, 80]

const pick = <T extends string>(v: string | null, options: { value: T | null }[]): T | null =>
  options.some((o) => o.value === v) ? (v as T) : null

export function parseFilters(p: URLSearchParams): JobFilters {
  const min = Number(p.get('min_score'))
  const before = p.get('deadline_before')
  return {
    type: pick(p.get('type'), TYPE_TABS),
    status: pick(p.get('status'), STATUS_OPTIONS) ?? 'ny',
    min_score: Number.isInteger(min) && min > 0 && min <= 100 ? min : null,
    source: pick(p.get('source'), SOURCE_OPTIONS),
    deadline_before: before && /^\d{4}-\d{2}-\d{2}$/.test(before) ? before : null,
    role: pick(p.get('role'), ROLE_OPTIONS),
    q: p.get('q') ?? '',
    sort: pick(p.get('sort'), SORT_OPTIONS) ?? 'deadline',
  }
}

const DEFAULTS: Partial<Record<keyof JobFilters, string>> = { status: 'ny', sort: 'deadline' }

/** Writes filters back to search params, leaving defaults out so URLs stay short. */
export function filtersToParams(f: JobFilters): URLSearchParams {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(f)) {
    if (v === null || v === '' || DEFAULTS[k as keyof JobFilters] === String(v)) continue
    p.set(k, String(v))
  }
  return p
}

export function toApiQuery(f: JobFilters): JobQuery {
  return {
    type: f.type ?? undefined,
    status: f.status === 'alle' ? undefined : f.status,
    min_score: f.min_score ?? undefined,
    source: f.source ?? undefined,
    deadline_before: f.deadline_before ?? undefined,
    role: f.role ?? undefined,
    q: f.q.trim() || undefined,
    sort: f.sort,
  }
}

/** Dimmed = triaged out of the current status filter; it stays until the list reloads. */
export const isDimmed = (job: Pick<JobListItem, 'status'>, f: JobFilters) => f.status !== 'alle' && job.status !== f.status

/** Number of filters set besides type tab and sort (for the mobile filter button). */
export function activeFilterCount(f: JobFilters) {
  return [f.status !== 'ny', f.min_score, f.source, f.deadline_before, f.role, f.q.trim()].filter(Boolean).length
}

export function useJobFilters() {
  const [params, setParams] = useSearchParams()
  const filters = useMemo(() => parseFilters(params), [params])
  const setFilters = useCallback(
    (patch: Partial<JobFilters>) => setParams((p) => filtersToParams({ ...parseFilters(p), ...patch }), { replace: true }),
    [setParams],
  )
  const reset = useCallback(() => setParams((p) => filtersToParams({ ...parseFilters(new URLSearchParams()), type: parseFilters(p).type }), { replace: true }), [setParams])
  return { filters, setFilters, reset, search: params.toString() }
}
