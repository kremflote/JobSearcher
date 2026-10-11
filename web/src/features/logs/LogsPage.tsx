import { format, parseISO } from 'date-fns'
import { nb } from 'date-fns/locale'
import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useAgentRunLog, useDiscardedLog, useRunLog } from '@/api/queries'
import type { AgentRunEntry, DiscardedEntry, RunLogEntry } from '@/api/types'
import { Tag } from '@/components/badges'
import { Page } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Segmented } from '@/features/drafts/Segmented'
import type { Tone } from '@/lib/format'

type Tab = 'kjoringer' | 'agentkall' | 'forkastet'
const TABS: { value: Tab; label: string }[] = [
  { value: 'kjoringer', label: 'Kjøringer' },
  { value: 'agentkall', label: 'Agentkall' },
  { value: 'forkastet', label: 'Forkastet' },
]

const SOURCE_LABEL: Record<string, string> = {
  finn_api: 'Finn',
  nav: 'NAV',
  teamtailor: 'Teamtailor',
  page_watch: 'Karrieresider',
  manual: 'Manuell',
}
const HEALTH: Record<RunLogEntry['health'], { label: string; tone: Tone }> = {
  ok: { label: 'OK', tone: 'good' },
  warn: { label: 'Advarsel', tone: 'warn' },
  fail: { label: 'Feil', tone: 'bad' },
}
/** Hard filter rules (`pipeline/hardfilter.py`). Unknown rules show their id. */
const RULE_LABEL: Record<string, string> = {
  job_type: 'Jobbtype',
  geography: 'Geografi',
  role: 'Rolle',
  occupation: 'Yrkeskategori',
  title_not_it: 'Ikke IT-tittel',
  seniority_title: 'Senioritet',
  experience_years: 'Erfaringskrav',
}

const time = (iso: string) => format(parseISO(iso), 'HH:mm', { locale: nb })
const day = (iso: string) => format(parseISO(iso), 'EEEE d. MMMM', { locale: nb })
const usd = (n: number) => (n === 0 ? '$0' : `$${n < 0.01 ? n.toFixed(4) : n.toFixed(3)}`)
const tokens = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1).replace('.', ',')}k` : String(n))
const seconds = (ms: number) => `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0).replace('.', ',')} s`

/** Groups rows by local day, newest first (the API already sorts newest first). */
function byDay<T>(rows: T[], at: (r: T) => string): [string, T[]][] {
  const groups = new Map<string, T[]>()
  for (const r of rows) {
    const key = format(parseISO(at(r)), 'yyyy-MM-dd')
    groups.set(key, [...(groups.get(key) ?? []), r])
  }
  return [...groups.entries()]
}

/** Logg (FRONTEND §5.8): runs per source, agent calls and jobs the hard filter discarded. */
export function LogsPage() {
  const [params, setParams] = useSearchParams()
  const tab = (TABS.find((t) => t.value === params.get('fane'))?.value ?? 'kjoringer') as Tab
  return (
    <Page title="Logg">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <Segmented<Tab>
          label="Logg"
          value={tab}
          options={TABS}
          onChange={(t) => setParams(t === 'kjoringer' ? {} : { fane: t }, { replace: true })}
          className="self-start"
        />
        {tab === 'kjoringer' ? <Runs /> : tab === 'agentkall' ? <AgentRuns /> : <Discarded />}
      </div>
    </Page>
  )
}

function Loaded<T>({
  query,
  empty,
  children,
}: {
  query: { isPending: boolean; isError: boolean; data?: { items: T[] }; refetch: () => unknown }
  empty: string
  children: (items: T[]) => ReactNode
}) {
  if (query.isPending)
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  if (query.isError || !query.data)
    return (
      <div className="text-sm">
        <p className="text-muted-foreground mb-2">Kunne ikke hente loggen.</p>
        <Button size="sm" variant="outline" onClick={() => query.refetch()}>
          Prøv igjen
        </Button>
      </div>
    )
  if (!query.data.items.length) return <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">{empty}</p>
  return <>{children(query.data.items)}</>
}

function DayGroups<T>({ rows, at, render }: { rows: T[]; at: (r: T) => string; render: (r: T) => ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      {byDay(rows, at).map(([key, items]) => (
        <section key={key} aria-label={day(at(items[0]!))}>
          <h2 className="text-muted-foreground mb-1.5 text-xs font-medium first-letter:uppercase">{day(at(items[0]!))}</h2>
          <ul className="divide-y rounded-lg border">{items.map(render)}</ul>
        </section>
      ))}
    </div>
  )
}

function Runs() {
  return (
    <Loaded<RunLogEntry> query={useRunLog()} empty="Ingen kjøringer ennå.">
      {(rows) => (
        <DayGroups
          rows={rows}
          at={(r) => r.started_at}
          render={(r) => (
            <li key={r.id} className="px-3 py-2 text-sm" data-testid="run-row">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-muted-foreground w-11 tabular-nums">{time(r.started_at)}</span>
                <span className="font-medium">{SOURCE_LABEL[r.source] ?? r.source}</span>
                <Tag tone={HEALTH[r.health].tone}>{HEALTH[r.health].label}</Tag>
                {r.trigger === 'manual' && <Tag tone="muted">Manuell</Tag>}
                <span className="text-muted-foreground ml-auto text-xs tabular-nums">
                  {r.found} funnet · {r.new} nye · {r.updated} oppdatert · {r.filtered_out} forkastet
                </span>
              </div>
              {r.errors.map((e, i) => (
                <p key={i} className="text-bad mt-1 text-xs break-words">
                  {e}
                </p>
              ))}
            </li>
          )}
        />
      )}
    </Loaded>
  )
}

function AgentRuns() {
  return (
    <Loaded<AgentRunEntry> query={useAgentRunLog()} empty="Ingen agentkall ennå.">
      {(rows) => (
        <DayGroups
          rows={rows}
          at={(r) => r.created_at}
          render={(r) => (
            <li key={r.id} className="px-3 py-2 text-sm" data-testid="agent-row">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-muted-foreground w-11 tabular-nums">{time(r.created_at)}</span>
                <span className="font-medium">{r.agent}</span>
                {r.status === 'error' && <Tag tone="bad">Feil</Tag>}
                <span className="text-muted-foreground min-w-0 truncate text-xs">
                  {r.model} · prompt {r.prompt_version}
                </span>
                <span className="text-muted-foreground ml-auto text-xs tabular-nums">
                  {tokens(r.input_tokens)} inn · {tokens(r.output_tokens)} ut · {usd(r.cost_usd)} · {seconds(r.duration_ms)}
                </span>
              </div>
              {r.error && <p className="text-bad mt-1 text-xs break-words">{r.error}</p>}
            </li>
          )}
        />
      )}
    </Loaded>
  )
}

function Discarded() {
  return (
    <Loaded<DiscardedEntry> query={useDiscardedLog()} empty="Hardfilteret har ikke forkastet noe ennå.">
      {(rows) => (
        <DayGroups
          rows={rows}
          at={(r) => r.created_at}
          render={(r) => (
            <li key={r.id} data-testid="discarded-row">
              <Link to={`/jobber/${r.job_id}`} className="hover:bg-muted/50 flex items-center gap-3 px-3 py-2 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{r.title}</p>
                  <p className="text-muted-foreground truncate text-xs">
                    {r.company}
                    {r.detail && ` · ${r.detail}`}
                  </p>
                </div>
                <Tag tone="muted">{RULE_LABEL[r.rule] ?? r.rule}</Tag>
                <span className="sr-only">Vis jobb</span>
                <ChevronRight className="text-muted-foreground size-4 shrink-0" aria-hidden />
              </Link>
            </li>
          )}
        />
      )}
    </Loaded>
  )
}
