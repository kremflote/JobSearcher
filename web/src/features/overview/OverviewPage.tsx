import { formatDistanceToNowStrict, parseISO } from 'date-fns'
import { nb } from 'date-fns/locale'
import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { useOverview } from '@/api/queries'
import type { ApplicationCard, JobListItem, JobType, Overview, SourceStatus } from '@/api/types'
import { DeadlineBadge, ScoreBadge, StatusBadge } from '@/components/badges'
import { Page } from '@/components/Page'
import { RunNowButton } from '@/components/tasks'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { deadlineInfo } from '@/lib/format'
import { JOB_TYPE_LABEL } from '@/lib/status'
import { cn } from '@/lib/utils'
import { SOURCE_OPTIONS } from '@/features/jobs/filters'
import { Card } from './Card'
import { LlmUsageCard } from './LlmUsageCard'

const SOURCE_LABEL = Object.fromEntries(SOURCE_OPTIONS.map((o) => [o.value, o.label])) as Record<string, string>
const TYPE_ORDER: JobType[] = ['permanent', 'trainee', 'graduate', 'summer', 'unknown']

export const ago = (iso: string) => formatDistanceToNowStrict(parseISO(iso), { locale: nb, addSuffix: true })

/** Oversikt `/` (FRONTEND §5.1). Source status and LLM usage sit under "Mer" on mobile. */
export function OverviewPage() {
  const { data, isPending, isError, refetch } = useOverview()

  return (
    <Page title="Oversikt">
      {isPending ? (
        <OverviewSkeleton />
      ) : isError ? (
        <div className="text-sm">
          <p className="text-muted-foreground mb-2">Fikk ikke kontakt med API-et.</p>
          <Button size="sm" variant="outline" onClick={() => refetch()}>
            Prøv igjen
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start" data-testid="overview">
          <div className="flex flex-col gap-4">
            <DeadlinesCard jobs={data.deadlines} />
            <NewSinceCard data={data.new_since_last} className="lg:hidden" />
            <FollowUpsCard items={data.follow_ups} />
          </div>
          <div className="flex flex-col gap-4">
            <NewSinceCard data={data.new_since_last} className="hidden lg:flex" />
            <div className="hidden flex-col gap-4 md:flex">
              <SourcesCard sources={data.sources} lastRunAt={data.last_run_at} />
              <LlmUsageCard />
            </div>
          </div>
        </div>
      )}
    </Page>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-muted-foreground px-3 py-4 text-sm">{children}</p>
}

function JobLine({ job, showStatus }: { job: JobListItem; showStatus?: boolean }) {
  const dl = deadlineInfo(job.deadline, job.deadline_text)
  return (
    <li>
      <Link to={`/jobber/${job.id}`} state={{ fromList: true }} className="hover:bg-accent/50 flex min-h-11 items-center gap-2 px-3 py-1.5 md:min-h-9">
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{job.title}</div>
          <div className="text-muted-foreground truncate text-xs">
            {job.company}
            {dl.date && ` · ${dl.date}`}
          </div>
        </div>
        {showStatus && <StatusBadge status={job.status} />}
        <ScoreBadge score={job.score} />
        <DeadlineBadge deadline={job.deadline} deadlineText={job.deadline_text} />
      </Link>
    </li>
  )
}

function DeadlinesCard({ jobs }: { jobs: JobListItem[] }) {
  return (
    <Card title="Frister neste 14 dager" testId="deadlines">
      {jobs.length ? (
        <ul className="divide-y">
          {jobs.map((j) => (
            <JobLine key={j.id} job={j} showStatus />
          ))}
        </ul>
      ) : (
        <Empty>Ingen frister for jobber du har markert som interessante.</Empty>
      )}
    </Card>
  )
}

function NewSinceCard({ data, className }: { data: Overview['new_since_last']; className?: string }) {
  const total = Object.values(data.counts_by_type).reduce((a, b) => a + (b ?? 0), 0)
  return (
    <Card
      title={`Nye siden sist${total ? ` (${total})` : ''}`}
      className={className}
      testId="new-since"
      action={
        <Link to="/jobber?sort=newest" className="text-muted-foreground hover:text-foreground inline-flex items-center text-xs">
          Se alle <ChevronRight className="size-3.5" />
        </Link>
      }
    >
      {total ? (
        <>
          <div className="flex flex-wrap gap-1.5 px-3 pt-2.5 pb-1">
            {TYPE_ORDER.filter((t) => data.counts_by_type[t]).map((t) => (
              <Link
                key={t}
                to={`/jobber?type=${t}&sort=newest`}
                className="bg-secondary hover:bg-accent rounded-full px-2.5 py-0.5 text-xs"
              >
                {JOB_TYPE_LABEL[t]} <span className="font-semibold tabular-nums">{data.counts_by_type[t]}</span>
              </Link>
            ))}
          </div>
          <ul className="divide-y">
            {data.top.map((j) => (
              <JobLine key={j.id} job={j} />
            ))}
          </ul>
        </>
      ) : (
        <Empty>Ingen nye jobber siden forrige kjøring.</Empty>
      )}
    </Card>
  )
}

function FollowUpsCard({ items }: { items: ApplicationCard[] }) {
  return (
    <Card title="Oppfølginger" testId="follow-ups">
      {items.length ? (
        <ul className="divide-y">
          {items.map((a) => {
            const due = [a.next_step_at, a.follow_up_at].filter((d): d is string => !!d).sort()[0] ?? null
            return (
              <li key={a.id}>
                <Link to={`/tracker?app=${a.id}`} className="hover:bg-accent/50 flex min-h-11 items-center gap-2 px-3 py-1.5 md:min-h-9">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">
                      {a.next_step ?? 'Følg opp søknaden'}
                    </div>
                    <div className="text-muted-foreground truncate text-xs">
                      {a.job_title} · {a.company}
                    </div>
                  </div>
                  <StatusBadge status={a.status} />
                  <DeadlineBadge deadline={due} />
                </Link>
              </li>
            )
          })}
        </ul>
      ) : (
        <Empty>Ingen oppfølginger de neste 7 dagene.</Empty>
      )}
    </Card>
  )
}

const HEALTH_CLASS: Record<NonNullable<SourceStatus['health']>, string> = {
  ok: 'bg-good',
  warn: 'bg-warn',
  fail: 'bg-bad',
}
const HEALTH_LABEL = { ok: 'OK', warn: 'Advarsel', fail: 'Feil' } as const

export function SourcesCard({ sources, lastRunAt }: { sources: SourceStatus[]; lastRunAt: string | null }) {
  return (
    <Card title="Kildestatus" testId="sources" action={<RunNowButton className="h-7" />}>
      <ul className="divide-y text-sm">
        {sources
          .filter((s) => s.last_run_at || s.health)
          .map((s) => (
            <li key={s.source} className="flex items-center gap-2 px-3 py-1.5">
              <span
                className={cn('size-2 shrink-0 rounded-full', s.health ? HEALTH_CLASS[s.health] : 'bg-muted-foreground/40')}
                aria-label={s.health ? HEALTH_LABEL[s.health] : 'Ukjent'}
                role="img"
              />
              <span className="w-24 shrink-0">{SOURCE_LABEL[s.source]}</span>
              <span className="text-muted-foreground min-w-0 flex-1 truncate text-xs" title={s.message ?? undefined}>
                {s.message ?? (s.found !== null ? `${s.found} funnet, ${s.new ?? 0} nye` : '')}
              </span>
              {s.last_run_at && <span className="text-muted-foreground shrink-0 text-xs">{ago(s.last_run_at)}</span>}
            </li>
          ))}
      </ul>
      {lastRunAt && <p className="text-muted-foreground border-t px-3 py-1.5 text-xs">Siste kjøring {ago(lastRunAt)}</p>}
    </Card>
  )
}

function OverviewSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-[3fr_2fr]" aria-busy="true">
      <Skeleton className="h-64" />
      <Skeleton className="h-64" />
    </div>
  )
}
