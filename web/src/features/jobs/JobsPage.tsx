import { Briefcase, Loader2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useJobs, type TriageStatus } from '@/api/queries'
import type { JobListItem } from '@/api/types'
import { Page } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useIsTabletUp, useIsWide } from '@/lib/useMediaQuery'
import { FilterRow, FilterSheetButton, TypeTabs } from './FilterBar'
import { isDimmed, toApiQuery, useJobFilters } from './filters'
import { JobDetailScreen, JobDetailView } from './JobDetail'
import { JobRow } from './JobRow'
import { useTriage } from './useTriage'

/**
 * `/jobber` and `/jobber/:id` (FRONTEND §5.2–5.3). ≥ 1024 px: master-detail with the detail in a
 * pane. Below that, `/jobber/:id` is its own screen.
 */
export function JobsRoute() {
  const { id } = useParams()
  const wide = useIsWide()
  const tabletUp = useIsTabletUp()
  if (id && !wide) return <JobDetailScreen actionBar={!tabletUp} />
  return <JobsPage selectedId={id ? Number(id) : null} wide={wide} />
}

const isTyping = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || ['INPUT', 'SELECT', 'TEXTAREA'].includes(t.tagName))

function JobsPage({ selectedId, wide }: { selectedId: number | null; wide: boolean }) {
  const navigate = useNavigate()
  const tabletUp = useIsTabletUp()
  const { filters, setFilters, reset, search } = useJobFilters()
  const query = useMemo(() => toApiQuery(filters), [filters])
  const list = useJobs(query)
  const jobs = useMemo(() => list.data?.pages.flatMap((p) => p.items) ?? [], [list.data])
  const total = list.data?.pages[0]?.total

  // Keyboard cursor below 1024 px; on wide screens the selection is the URL.
  const [cursor, setCursor] = useState<number | null>(null)
  const activeId = wide ? selectedId : cursor
  const qs = search ? `?${search}` : ''

  const select = useCallback(
    (id: number | null) => {
      if (wide) navigate({ pathname: id ? `/jobber/${id}` : '/jobber', search }, { replace: true })
      else setCursor(id)
    },
    [wide, navigate, search],
  )

  const { triage, undo } = useTriage(select)

  /** Triage and move on to the next job still in the filter (FRONTEND §5.2). */
  const triageAndNext = useCallback(
    (job: Pick<JobListItem, 'id' | 'title' | 'status'>, status: TriageStatus, advance: boolean) => {
      if (!triage(job, status)) return
      if (!advance) return
      const i = jobs.findIndex((j) => j.id === job.id)
      const next = jobs.slice(i + 1).find((j) => !isDimmed(j, filters)) ?? jobs[i + 1]
      if (next) select(next.id)
    },
    [triage, jobs, filters, select],
  )

  // Keep the active row in view while moving with j/k.
  const rowRefs = useRef(new Map<number, HTMLLIElement>())
  useEffect(() => {
    if (activeId !== null) rowRefs.current.get(activeId)?.scrollIntoView?.({ block: 'nearest' })
  }, [activeId])

  // Keyboard triage on PC: j/k, i, x, u, o, Enter.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || isTyping(e.target)) return
      const i = jobs.findIndex((j) => j.id === activeId)
      const job = i >= 0 ? jobs[i] : undefined
      switch (e.key) {
        case 'j': {
          const next = jobs[Math.min(jobs.length - 1, i + 1)]
          if (next) select(next.id)
          if (i >= jobs.length - 3 && list.hasNextPage && !list.isFetchingNextPage) list.fetchNextPage()
          break
        }
        case 'k': {
          const prev = jobs[Math.max(0, i - 1)]
          if (prev) select(prev.id)
          break
        }
        case 'i':
          if (job) triageAndNext(job, job.status === 'interessant' ? 'ny' : 'interessant', job.status !== 'interessant')
          break
        case 'x':
          if (job) triageAndNext(job, job.status === 'ikke_aktuell' ? 'ny' : 'ikke_aktuell', job.status !== 'ikke_aktuell')
          break
        case 'u':
          undo()
          break
        case 'o':
          if (job?.application_url) window.open(job.application_url, '_blank', 'noreferrer')
          break
        case 'Enter':
          if (job && !wide) navigate({ pathname: `/jobber/${job.id}`, search }, { state: { fromList: true } })
          else return
          break
        default:
          return
      }
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [jobs, activeId, select, triageAndNext, undo, wide, navigate, search, list])

  // Infinite scroll: load the next page when the sentinel comes into view.
  const sentinel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = sentinel.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting) && list.hasNextPage && !list.isFetchingNextPage) list.fetchNextPage()
    })
    io.observe(el)
    return () => io.disconnect()
  }, [list])

  const listBody = list.isPending ? (
    <ListSkeleton />
  ) : list.isError ? (
    <div className="p-4 text-sm">
      <p className="text-muted-foreground mb-2">Kunne ikke hente jobbene.</p>
      <Button size="sm" variant="outline" onClick={() => list.refetch()}>
        Prøv igjen
      </Button>
    </div>
  ) : jobs.length === 0 ? (
    <div className="text-muted-foreground p-6 text-center text-sm">
      <p>Ingen jobber med disse filtrene.</p>
      <Button size="sm" variant="link" onClick={reset}>
        Nullstill filtre
      </Button>
    </div>
  ) : (
    <>
      <ul className="divide-y" aria-label="Jobber" data-testid="job-list">
        {jobs.map((job) => (
          <JobRow
            key={job.id}
            ref={(el) => {
              if (el) rowRefs.current.set(job.id, el)
              else rowRefs.current.delete(job.id)
            }}
            job={job}
            href={`/jobber/${job.id}${qs}`}
            active={job.id === activeId}
            dimmed={isDimmed(job, filters)}
            swipe={!tabletUp}
            onSelect={() => setCursor(job.id)}
            onTriage={(status) => triageAndNext(job, status, false)}
          />
        ))}
      </ul>
      <div ref={sentinel} className="flex justify-center p-3">
        {list.hasNextPage && (
          <Button size="sm" variant="ghost" onClick={() => list.fetchNextPage()} disabled={list.isFetchingNextPage}>
            {list.isFetchingNextPage && <Loader2 className="animate-spin" />}
            Last flere
          </Button>
        )}
      </div>
    </>
  )

  const listColumn = (
    <>
      <TypeTabs filters={filters} setFilters={setFilters} />
      {tabletUp && <FilterRow filters={filters} setFilters={setFilters} reset={reset} />}
      {listBody}
    </>
  )

  return (
    <Page
      title="Jobber"
      className="p-0"
      actions={
        <>
          {total !== undefined && (
            <span className="text-muted-foreground text-xs tabular-nums" data-testid="job-count">
              {total} jobber
            </span>
          )}
          {!tabletUp && <FilterSheetButton filters={filters} setFilters={setFilters} reset={reset} />}
        </>
      }
    >
      {wide ? (
        <div className="grid h-[calc(100dvh-3rem)] grid-cols-[minmax(22rem,26rem)_1fr]">
          <div className="overflow-y-auto border-r">{listColumn}</div>
          <div className="overflow-y-auto" data-testid="detail-pane">
            {selectedId ? (
              <JobDetailView
                key={selectedId}
                id={selectedId}
                actionBar={false}
                onTriage={(job, status) => triageAndNext(job, status, status !== 'ny')}
              />
            ) : (
              <div className="text-muted-foreground flex h-full flex-col items-center justify-center gap-2 text-sm">
                <Briefcase className="size-6" aria-hidden />
                Velg en jobb, eller trykk <kbd className="bg-muted rounded px-1">j</kbd>
              </div>
            )}
          </div>
        </div>
      ) : (
        listColumn
      )}
    </Page>
  )
}

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-3 p-3" aria-busy="true">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="flex flex-col gap-1.5">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ))}
    </div>
  )
}
