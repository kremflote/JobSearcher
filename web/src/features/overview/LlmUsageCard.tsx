import { format, formatDistanceToNowStrict, parseISO } from 'date-fns'
import { nb } from 'date-fns/locale'
import { AlertTriangle, ChevronRight } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { useLlmUsage } from '@/api/queries'
import type { LlmBackendUsage, LlmUsage, OpenRouterBalance } from '@/api/types'
import { Sheet } from '@/components/Sheet'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useIsWide } from '@/lib/useMediaQuery'
import { cn } from '@/lib/utils'
import { Card } from './Card'
import {
  BACKEND_COLOR,
  BACKEND_LABEL,
  BACKEND_ORDER,
  BALANCE_SOURCE_LABEL,
  balanceState,
  balanceText,
  capPercent,
  count,
  dailySeries,
  dayLabel,
  fallbackCalls,
  LOW_BALANCE_USD,
  tokens,
  usd,
} from './llmUsage'

const Code = ({ children }: { children: ReactNode }) => (
  <code className="bg-muted rounded px-1 py-0.5 font-mono text-[0.85em]">{children}</code>
)

/**
 * LLM-forbruk (FRONTEND §5.1, F2b): month cost against the cap, OpenRouter balance and fallback
 * calls. Clicking opens the detail: side panel on PC, action sheet below 1024 px.
 */
export function LlmUsageCard() {
  const { data, isPending, isError, refetch } = useLlmUsage()
  const wide = useIsWide()
  const [open, setOpen] = useState(false)
  const openDetail = () => setOpen(true)

  return (
    <>
      <Card
        title="LLM-forbruk"
        testId="llm-usage"
        onClick={data ? openDetail : undefined}
        className={cn(data && 'hover:bg-accent/30 cursor-pointer')}
        action={
          data && (
            <Button size="xs" variant="ghost" className="text-muted-foreground" onClick={openDetail} aria-haspopup="dialog">
              Detaljer <ChevronRight />
            </Button>
          )
        }
      >
        {isPending ? (
          <div className="flex flex-col gap-2 px-3 py-2.5" aria-busy="true">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-1.5 w-full" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : isError ? (
          <div className="px-3 py-2.5 text-sm">
            <p className="text-muted-foreground mb-2">Kunne ikke hente LLM-forbruket.</p>
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              Prøv igjen
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-2.5 px-3 py-2.5 text-sm">
            <CapMeter usage={data} />
            <BalanceLine balance={data.openrouter} />
            <p className="text-muted-foreground text-xs">
              Reservekall denne måneden: <span className="text-foreground font-medium tabular-nums">{fallbackCalls(data)}</span>
            </p>
          </div>
        )}
      </Card>
      {/* Outside the card, so clicks in the portal don't bubble into the card's onClick. */}
      <Sheet open={open && !!data} onOpenChange={setOpen} title="LLM-forbruk" side={wide ? 'right' : 'bottom'}>
        {data && <LlmUsageDetail usage={data} className={wide ? 'p-4' : undefined} />}
      </Sheet>
    </>
  )
}

function CapMeter({ usage }: { usage: LlmUsage }) {
  const pct = capPercent(usage.spent_usd, usage.cap_usd)
  return (
    <div data-warn={usage.warn || undefined}>
      <p className="text-muted-foreground mb-1 text-xs" data-testid="llm-cap-label">
        Kostnadstak for betalte kall (Claude-abonnementet teller ikke)
      </p>
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-semibold tabular-nums" data-testid="llm-spent">
          {usd(usage.spent_usd)}
        </span>
        <span className="text-muted-foreground text-xs tabular-nums">
          av {usd(usage.cap_usd, { whole: true })} denne måneden ({pct} %)
        </span>
      </div>
      <div
        className="bg-muted mt-1.5 h-1.5 overflow-hidden rounded-full"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Andel av kostnadstaket"
      >
        <div className={cn('h-full rounded-full', usage.warn ? 'bg-warn' : 'bg-foreground/60')} style={{ width: `${pct}%` }} />
      </div>
      {usage.warn && (
        <p className="text-warn mt-1.5 flex items-center gap-1 text-xs">
          <AlertTriangle className="size-3.5" aria-hidden /> Nærmer seg kostnadstaket.
        </p>
      )}
    </div>
  )
}

function BalanceLine({ balance }: { balance: OpenRouterBalance }) {
  const state = balanceState(balance)
  return (
    <div className="flex items-center justify-between gap-2" data-testid="llm-balance" data-state={state}>
      <span className="text-muted-foreground text-xs">OpenRouter-saldo</span>
      {state === 'unset' ? (
        <span className="text-muted-foreground text-xs">OpenRouter ikke satt opp</span>
      ) : state === 'unknown' ? (
        <span className="text-muted-foreground text-xs">Ukjent</span>
      ) : (
        <span className={cn('flex items-center gap-1 text-xs font-medium tabular-nums', state === 'low' && 'text-bad')}>
          {state === 'low' && <AlertTriangle className="size-3.5" aria-label="Lav saldo" role="img" />}
          {balanceText(balance)}
        </span>
      )}
    </div>
  )
}

/** The detail: per backend, per day and the balance. */
export function LlmUsageDetail({ usage, className }: { usage: LlmUsage; className?: string }) {
  const backends = [...usage.by_backend].sort((a, b) => BACKEND_ORDER.indexOf(a.backend) - BACKEND_ORDER.indexOf(b.backend))
  return (
    <div className={cn('flex flex-col gap-6 text-sm', className)} data-testid="llm-usage-detail">
      <Section title={`Denne måneden (siden ${format(parseISO(usage.month_start), 'd. MMM', { locale: nb }).replace(/\.$/, '')})`}>
        <CapMeter usage={usage} />
      </Section>

      <Section title="Per backend">
        <ul className="flex flex-col gap-2">
          {backends.map((b) => (
            <BackendRow key={b.backend} usage={b} />
          ))}
        </ul>
      </Section>

      <Section title="Tokens per dag, siste 30 dager">
        <DailyChart usage={usage} />
      </Section>

      <Section title="Saldo hos OpenRouter">
        <BalanceDetail balance={usage.openrouter} />
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">{title}</h3>
      {children}
    </section>
  )
}

const Swatch = ({ className }: { className: string }) => (
  <span className={cn('inline-block size-2.5 shrink-0 rounded-sm', className)} aria-hidden />
)

function BackendRow({ usage: b }: { usage: LlmBackendUsage }) {
  return (
    <li className="rounded-md border px-3 py-2" data-testid={`llm-backend-${b.backend}`}>
      <div className="flex items-center gap-2">
        <Swatch className={BACKEND_COLOR[b.backend]} />
        <span className="font-medium">{BACKEND_LABEL[b.backend]}</span>
        <span
          className={cn(
            'ml-auto rounded px-1.5 py-0.5 text-[11px] font-medium',
            b.estimated ? 'bg-secondary text-muted-foreground' : 'bg-info-soft text-info',
          )}
        >
          {b.estimated ? 'estimat, fra abonnementet' : 'betalt'}
        </span>
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
        <Stat label="Kall">
          {count(b.calls)}
          {b.fallback_calls > 0 && <span className="text-muted-foreground"> ({b.fallback_calls} reserve)</span>}
        </Stat>
        <Stat label="Tokens inn">{tokens(b.input_tokens)}</Stat>
        <Stat label="Tokens ut">{tokens(b.output_tokens)}</Stat>
        <Stat label="Kostnad">{usd(b.cost_usd)}</Stat>
      </dl>
    </li>
  )
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium tabular-nums">{children}</dd>
    </div>
  )
}

/** Stacked bars of tokens per day and backend. Clicking a bar shows that day's numbers. */
function DailyChart({ usage }: { usage: LlmUsage }) {
  const series = useMemo(() => dailySeries(usage.daily), [usage.daily])
  const [selected, setSelected] = useState(series.length - 1)
  const max = Math.max(1, ...series.map((d) => d.total))
  const day = series[selected]!
  const present = BACKEND_ORDER.filter((b) => usage.by_backend.some((u) => u.backend === b))

  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-28 items-end gap-px" role="group" aria-label="Tokens per dag">
        {series.map((d, i) => (
          <button
            key={d.date}
            type="button"
            data-testid="llm-day"
            data-date={d.date}
            aria-pressed={i === selected}
            aria-label={`${dayLabel(d.date)}: ${count(d.total)} tokens`}
            title={`${dayLabel(d.date)}: ${tokens(d.total)} tokens`}
            onClick={() => setSelected(i)}
            className={cn(
              'focus-visible:ring-ring flex h-full min-w-0 flex-1 flex-col-reverse overflow-hidden rounded-sm outline-none focus-visible:ring-2',
              i === selected ? 'bg-accent ring-foreground/30 ring-1' : 'hover:bg-accent/60',
            )}
          >
            {d.rows.map((r) => (
              <span
                key={r.backend}
                className={cn('block w-full shrink-0', BACKEND_COLOR[r.backend])}
                style={{ height: `${((r.input_tokens + r.output_tokens) / max) * 100}%` }}
              />
            ))}
          </button>
        ))}
      </div>
      <div className="text-muted-foreground flex justify-between text-[11px]">
        <span>{dayLabel(series[0]!.date)}</span>
        <span>i dag</span>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {present.map((b) => (
          <span key={b} className="flex items-center gap-1.5">
            <Swatch className={BACKEND_COLOR[b]} />
            {BACKEND_LABEL[b]}
          </span>
        ))}
      </div>

      <div className="bg-muted/50 rounded-md px-3 py-2" data-testid="llm-day-detail" aria-live="polite">
        <div className="mb-1 font-medium">
          {format(parseISO(day.date), 'EEEE d. MMMM', { locale: nb })}
          {day.total > 0 && <span className="text-muted-foreground font-normal"> · {count(day.total)} tokens</span>}
        </div>
        {day.rows.length ? (
          <ul className="flex flex-col gap-1 text-xs">
            {day.rows.map((r) => (
              <li key={r.backend} className="flex flex-wrap items-center gap-x-2">
                <Swatch className={BACKEND_COLOR[r.backend]} />
                <span className="min-w-0 flex-1">{BACKEND_LABEL[r.backend]}</span>
                <span className="text-muted-foreground tabular-nums">
                  {tokens(r.input_tokens)} inn · {tokens(r.output_tokens)} ut · {usd(r.cost_usd)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted-foreground text-xs">Ingen kall denne dagen.</p>
        )}
      </div>
    </div>
  )
}

function BalanceDetail({ balance }: { balance: OpenRouterBalance }) {
  const state = balanceState(balance)
  if (state === 'unset')
    return (
      <div data-testid="llm-balance-detail" data-state={state}>
        <p className="font-medium">OpenRouter ikke satt opp</p>
        <p className="text-muted-foreground mt-1 text-xs">
          Uten <Code>OPENROUTER_API_KEY</Code> i <Code>.env</Code> scores ingen jobber, med mindre{' '}
          <Code>llm.backend</Code> er satt til <Code>claude_code</Code>.
        </p>
      </div>
    )
  if (state === 'unknown')
    return (
      <div data-testid="llm-balance-detail" data-state={state}>
        <p className="font-medium">Saldo ukjent</p>
        <p className="text-muted-foreground mt-1 text-xs">
          Bare forbruket vises. Slå på saldoen ved å sette en kredittgrense på nøkkelen hos OpenRouter, eller legg inn{' '}
          <Code>OPENROUTER_MANAGEMENT_KEY</Code> i <Code>.env</Code>.
        </p>
        {balance.used_usd != null && (
          <p className="mt-1 text-xs" data-testid="llm-used">
            Brukt totalt: {usd(balance.used_usd)}{' '}
            <span className="text-muted-foreground">(hos OpenRouter, også kall utenfor appen)</span>
          </p>
        )}
      </div>
    )
  return (
    <div className="flex flex-col gap-2" data-testid="llm-balance-detail" data-state={state}>
      <p className={cn('text-base font-semibold tabular-nums', state === 'low' && 'text-bad')}>{balanceText(balance)}</p>
      {state === 'low' && (
        <p className="bg-bad-soft text-bad flex items-start gap-1.5 rounded-md px-2.5 py-2 text-xs" role="alert">
          <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden />
          Under {usd(LOW_BALANCE_USD, { whole: true })} igjen. Fyll på kreditt hos OpenRouter, ellers stopper AI-scoringen.
        </p>
      )}
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="text-muted-foreground">Brukt totalt</dt>
        <dd data-testid="llm-used">
          {balance.used_usd != null ? usd(balance.used_usd) : 'ukjent'}{' '}
          <span className="text-muted-foreground">(hos OpenRouter, også kall utenfor appen)</span>
        </dd>
        <dt className="text-muted-foreground">Kilde</dt>
        <dd>{BALANCE_SOURCE_LABEL[balance.balance_source!]}</dd>
        <dt className="text-muted-foreground">Sist hentet</dt>
        <dd title={balance.fetched_at ? format(parseISO(balance.fetched_at), "d. MMM yyyy 'kl.' HH:mm", { locale: nb }) : undefined}>
          {balance.fetched_at
            ? formatDistanceToNowStrict(parseISO(balance.fetched_at), { locale: nb, addSuffix: true })
            : 'ikke hentet'}
        </dd>
      </dl>
    </div>
  )
}
