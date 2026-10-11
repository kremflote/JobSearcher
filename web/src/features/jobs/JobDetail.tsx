import { format, parseISO } from 'date-fns'
import { nb } from 'date-fns/locale'
import { ArrowLeft, Check, ExternalLink, FileText, Mail, Phone, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, type ReactNode } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { useJob, useJobs, type TriageStatus } from '@/api/queries'
import type { JobDetail } from '@/api/types'
import { DeadlineBadge, ScoreBadge, StatusBadge, Tag } from '@/components/badges'
import { Markdown } from '@/components/Markdown'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { deadlineInfo } from '@/lib/format'
import { JOB_TYPE_LABEL } from '@/lib/status'
import { cn } from '@/lib/utils'
import { StartDraftButton } from '@/features/drafts/StartDraftButton'
import { isDimmed, SOURCE_OPTIONS, toApiQuery, useJobFilters } from './filters'
import { canTriage, useTriage } from './useTriage'

const SOURCE_LABEL = Object.fromEntries(SOURCE_OPTIONS.map((o) => [o.value, o.label])) as Record<string, string>
const REMOTE_LABEL = { none: null, hybrid: 'Hybrid', full: 'Fjernarbeid' } as const

const fmtDate = (iso: string) => format(parseISO(iso), 'd. MMM yyyy', { locale: nb })

type TriageFn = (job: JobDetail, status: TriageStatus) => void

/** Job detail body (FRONTEND §5.3), used in the PC detail pane and the mobile screen. */
export function JobDetailView({ id, onTriage, actionBar }: { id: number; onTriage: TriageFn; actionBar: boolean }) {
  const { data: job, isPending, isError, refetch } = useJob(id)

  if (isPending) return <DetailSkeleton />
  if (isError)
    return (
      <div className="p-4 text-sm">
        <p className="text-muted-foreground mb-2">Kunne ikke hente jobben.</p>
        <Button size="sm" variant="outline" onClick={() => refetch()}>
          Prøv igjen
        </Button>
      </div>
    )

  const ev = job.evaluation
  const dl = deadlineInfo(job.deadline, job.deadline_text)
  const remote = job.remote ? REMOTE_LABEL[job.remote] : null

  return (
    <article className={cn('flex flex-col gap-5 p-4', actionBar && 'pb-20')} data-testid="job-detail">
      {/* 1. Title, company, place, type, score */}
      <header className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-lg leading-tight font-semibold">{job.title}</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            {job.company}
            {job.location_text && ` · ${job.location_text}`}
            {remote && ` · ${remote}`}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <Tag>{JOB_TYPE_LABEL[job.job_type]}</Tag>
            {job.is_new && <Tag tone="good" title="Ny siden forrige kjøring">Ny</Tag>}
            {job.reposted && <Tag>Lagt ut på nytt</Tag>}
            <StatusBadge status={job.status} />
          </div>
        </div>
        <ScoreBadge score={job.score} className="h-7 min-w-9 text-sm" />
      </header>

      {/* 2. Deadline, apply link, status buttons */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="mr-auto text-sm">
          <span className="text-muted-foreground">Frist </span>
          {dl.date ? (
            <>
              <span className="font-medium">{dl.date}</span> <DeadlineBadge deadline={job.deadline} />
            </>
          ) : (
            <span className="font-medium">{job.deadline_text ?? 'ukjent'}</span>
          )}
        </div>
        {!actionBar && <TriageButtons job={job} onTriage={onTriage} />}
        {!actionBar && <ApplyLink job={job} />}
      </div>

      {/* 3. Draft or open application */}
      <div>
        {job.application?.latest_draft_id ? (
          <Button asChild size="sm" variant="secondary">
            <Link to={`/soknader/${job.application.id}`}>
              <FileText /> Åpne søknad
            </Link>
          </Button>
        ) : (
          <StartDraftButton jobId={job.id} />
        )}
      </div>

      {/* 4. Why it matches, concerns */}
      {ev && (ev.match_reasons.length > 0 || ev.concerns.length > 0) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {ev.match_reasons.length > 0 && (
            <Section title="Hvorfor match">
              <BulletList items={ev.match_reasons} icon={<Check className="text-good size-4" />} />
            </Section>
          )}
          {ev.concerns.length > 0 && (
            <Section title="Bekymringer">
              <BulletList items={ev.concerns} icon={<X className="text-warn size-4" />} />
            </Section>
          )}
        </div>
      )}

      {/* 5. Summary, key requirements */}
      {ev && (
        <Section title="Sammendrag">
          <p className="text-sm">{ev.summary}</p>
          {ev.confidence === 'low' && <p className="text-muted-foreground mt-1 text-xs">Lav sikkerhet: vurdert på lite informasjon.</p>}
          {ev.key_requirements.length > 0 && (
            <>
              <h4 className="text-muted-foreground mt-3 mb-1 text-xs font-medium">Nøkkelkrav</h4>
              <ul className="list-disc pl-5 text-sm">
                {ev.key_requirements.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </>
          )}
          {ev.tech.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1">
              {ev.tech.map((t) => (
                <Tag key={t}>{t}</Tag>
              ))}
            </div>
          )}
        </Section>
      )}

      {/* 6. Contacts */}
      {job.contacts.length > 0 && (
        <Section title="Kontaktpersoner">
          <ul className="flex flex-col gap-2 text-sm">
            {job.contacts.map((c) => (
              <li key={c.name}>
                <div className="font-medium">
                  {c.name}
                  {c.role && <span className="text-muted-foreground font-normal"> · {c.role}</span>}
                </div>
                <div className="mt-0.5 flex flex-wrap gap-x-4 gap-y-1">
                  {c.email && (
                    <a href={`mailto:${c.email}`} className="text-info inline-flex items-center gap-1 hover:underline">
                      <Mail className="size-3.5" /> {c.email}
                    </a>
                  )}
                  {c.phone && (
                    <a href={`tel:${c.phone.replace(/\s/g, '')}`} className="text-info inline-flex items-center gap-1 hover:underline">
                      <Phone className="size-3.5" /> {c.phone}
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* 7. Ad text */}
      <Section title="Annonse">
        {job.description ? (
          <>
            <Markdown text={job.description} className="text-sm leading-relaxed" />
            {job.source_refs[0]?.url && (
              <p className="text-muted-foreground mt-2 text-xs">
                Kilde:{' '}
                <a href={job.source_refs[0].url} target="_blank" rel="noreferrer" className="hover:underline">
                  {SOURCE_LABEL[job.source_refs[0].source]}
                </a>
              </p>
            )}
          </>
        ) : (
          <p className="text-muted-foreground text-sm">
            Bare tittel kjent.{' '}
            {(job.source_refs[0]?.url ?? job.application_url) && (
              <a href={job.source_refs[0]?.url ?? job.application_url!} target="_blank" rel="noreferrer" className="text-info hover:underline">
                Les annonsen hos kilden
              </a>
            )}
          </p>
        )}
      </Section>

      {/* 8. Company note */}
      {job.company_note && (
        <details className="group rounded-lg border px-3 py-2">
          <summary className="cursor-pointer text-sm font-medium">
            Bedriftsnotat
            {job.company_note.quality === 'limited' && <span className="text-muted-foreground font-normal"> · begrenset</span>}
          </summary>
          <Markdown text={job.company_note.content} className="mt-2 text-sm" />
          <p className="text-muted-foreground mt-2 text-xs">Undersøkt {fmtDate(job.company_note.researched_at)}</p>
        </details>
      )}

      {/* 9. Sources and history */}
      <Section title="Kilder og historikk">
        <ul className="text-muted-foreground flex flex-col gap-1 text-xs">
          {job.source_refs.map((r) => (
            <li key={`${r.source}-${r.source_id}`}>
              {r.url ? (
                <a href={r.url} target="_blank" rel="noreferrer" className="hover:underline">
                  {SOURCE_LABEL[r.source]}
                </a>
              ) : (
                SOURCE_LABEL[r.source]
              )}
              {` · hentet ${fmtDate(r.fetched_at)}`}
            </li>
          ))}
          <li>Først sett {fmtDate(job.first_seen)}, sist sett {fmtDate(job.last_seen)}</li>
          {job.reposted_from_id && <li>Lagt ut på nytt (tidligere annonse #{job.reposted_from_id})</li>}
        </ul>
      </Section>

      {actionBar && <ActionBar job={job} onTriage={onTriage} />}
    </article>
  )
}

function TriageButtons({ job, onTriage, big }: { job: JobDetail; onTriage: TriageFn; big?: boolean }) {
  if (!canTriage(job.status))
    return job.application ? (
      <Link to={`/tracker?app=${job.application.id}`} className="text-primary text-sm underline-offset-4 hover:underline">
        Endre status i Tracker
      </Link>
    ) : (
      <span className="text-muted-foreground text-xs">Status endres i Tracker</span>
    )
  const size = big ? 'default' : 'sm'
  return (
    <>
      <Button
        size={size}
        variant={job.status === 'interessant' ? 'default' : 'outline'}
        aria-pressed={job.status === 'interessant'}
        onClick={() => onTriage(job, job.status === 'interessant' ? 'ny' : 'interessant')}
        className={cn(big && 'flex-1')}
      >
        <Check /> Interessant
      </Button>
      <Button
        size={size}
        variant={job.status === 'ikke_aktuell' ? 'default' : 'outline'}
        aria-pressed={job.status === 'ikke_aktuell'}
        onClick={() => onTriage(job, job.status === 'ikke_aktuell' ? 'ny' : 'ikke_aktuell')}
        className={cn(big && 'flex-1')}
      >
        <X /> Ikke aktuell
      </Button>
    </>
  )
}

function ApplyLink({ job, big }: { job: JobDetail; big?: boolean }) {
  if (!job.application_url) return null
  return (
    <Button asChild size={big ? 'default' : 'sm'} variant={big ? 'secondary' : 'outline'}>
      <a href={job.application_url} target="_blank" rel="noreferrer">
        Søk <ExternalLink />
      </a>
    </Button>
  )
}

/** Mobile: fixed action bar above the bottom tabs (FRONTEND §5.3). */
function ActionBar({ job, onTriage }: { job: JobDetail; onTriage: TriageFn }) {
  // Lifts toasts and the task indicator above the bar (index.css `.above-action-bar`).
  useEffect(() => {
    document.body.dataset.actionBar = ''
    return () => {
      delete document.body.dataset.actionBar
    }
  }, [])
  return (
    <div
      className="bg-background/95 fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-30 flex gap-2 border-t p-2 backdrop-blur"
      data-testid="action-bar"
    >
      <TriageButtons job={job} onTriage={onTriage} big />
      <ApplyLink job={job} big />
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-1.5 text-sm font-semibold">{title}</h3>
      {children}
    </section>
  )
}

function BulletList({ items, icon }: { items: string[]; icon: ReactNode }) {
  return (
    <ul className="flex flex-col gap-1 text-sm">
      {items.map((t) => (
        <li key={t} className="flex gap-1.5">
          <span className="mt-0.5 shrink-0">{icon}</span>
          {t}
        </li>
      ))}
    </ul>
  )
}

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-3 p-4" aria-busy="true">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  )
}

/**
 * `/jobber/:id` below 1024 px: its own screen with a back button and the action bar on mobile.
 * Triage moves straight on to the next job in the list (same filters), so a day can be triaged
 * without going back to the list (FRONTEND §5.3).
 */
export function JobDetailScreen({ actionBar }: { actionBar: boolean }) {
  const { id: rawId } = useParams()
  const id = Number(rawId)
  const navigate = useNavigate()
  const location = useLocation()
  const fromList = (location.state as { fromList?: boolean } | null)?.fromList === true
  const back = useCallback(
    () => (fromList ? navigate(-1) : navigate({ pathname: '/jobber', search: location.search })),
    [fromList, navigate, location.search],
  )
  const show = useCallback(
    // Replace, so Tilbake still returns to the list rather than through every triaged job.
    (jobId: number) => navigate({ pathname: `/jobber/${jobId}`, search: location.search }, { replace: true, state: { fromList } }),
    [navigate, location.search, fromList],
  )

  const { filters } = useJobFilters()
  const list = useJobs(useMemo(() => toApiQuery(filters), [filters]))

  /** The next job after `id` that is still in the filter, loading more pages if needed. */
  const nextJob = useCallback(async () => {
    let data = list.data
    for (;;) {
      const jobs = data?.pages.flatMap((p) => p.items) ?? []
      const i = jobs.findIndex((j) => j.id === id)
      if (i < 0) return null
      const next = jobs.slice(i + 1).find((j) => !isDimmed(j, filters))
      if (next) return next
      if (!data?.pages.at(-1)?.next_cursor) return null
      data = (await list.fetchNextPage()).data
    }
  }, [list, id, filters])

  const { triage } = useTriage(show)

  return (
    <div className="flex min-h-full flex-col">
      <header className="bg-background/95 sticky top-0 z-30 flex h-12 items-center gap-1 border-b px-2 backdrop-blur">
        <Button size="icon-sm" variant="ghost" onClick={back} aria-label="Tilbake">
          <ArrowLeft />
        </Button>
        <h1 className="truncate text-base font-semibold">Jobb</h1>
      </header>
      <JobDetailView
        key={id}
        id={id}
        actionBar={actionBar}
        onTriage={async (job, status) => {
          if (!triage(job, status) || status === 'ny') return
          const next = await nextJob()
          if (next) show(next.id)
          else back()
        }}
      />
    </div>
  )
}
