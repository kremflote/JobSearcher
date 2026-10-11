import { format, isToday, parseISO } from 'date-fns'
import { nb } from 'date-fns/locale'
import { Bot, Check, RotateCcw, UserRound, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useDraft } from '@/api/queries'
import type { DraftSummary } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { diffStats, diffWords } from './diff'
import { DiffText } from './DiffText'
import { Segmented } from './Segmented'

export const fmtVersionTime = (iso: string) => {
  const d = parseISO(iso)
  return isToday(d) ? `i dag ${format(d, 'HH:mm')}` : format(d, "d. MMM 'kl.' HH:mm", { locale: nb })
}

export const authorLabel = (v: DraftSummary) => (v.author === 'agent' ? 'Agenten' : 'Deg')

/** One line per version, newest first (mobile "Versjoner", PC version menu). */
export function VersionList({
  versions,
  currentId,
  onSelect,
}: {
  versions: DraftSummary[]
  currentId: number | null
  onSelect: (id: number) => void
}) {
  return (
    <ul className="divide-y rounded-lg border" data-testid="version-list">
      {[...versions].reverse().map((v) => (
        <li key={v.id}>
          <button
            type="button"
            onClick={() => onSelect(v.id)}
            className="hover:bg-muted/50 flex w-full items-start gap-2 px-3 py-2 text-left text-sm"
          >
            {v.author === 'agent' ? (
              <Bot className="text-muted-foreground mt-0.5 size-4 shrink-0" aria-hidden />
            ) : (
              <UserRound className="text-muted-foreground mt-0.5 size-4 shrink-0" aria-hidden />
            )}
            <span className="min-w-0 flex-1">
              <span className="font-medium">Versjon {v.version}</span>
              <span className="text-muted-foreground"> · {authorLabel(v)} · {fmtVersionTime(v.created_at)}</span>
              {(v.change_summary || v.instruction) && (
                <span className="text-muted-foreground block truncate">{v.change_summary ?? v.instruction}</span>
              )}
            </span>
            {v.id === currentId && (
              <span className="text-good flex items-center gap-0.5 text-xs">
                <Check className="size-3.5" aria-hidden /> Gjeldende
              </span>
            )}
          </button>
        </li>
      ))}
    </ul>
  )
}

type Against = 'previous' | 'current'

/**
 * One older version shown as a word diff against the version before it or against the current
 * one (FRONTEND §5.5), with "Gjenopprett" to make it the current text again.
 */
export function VersionView({
  versions,
  selectedId,
  currentId,
  onRestore,
  onClose,
}: {
  versions: DraftSummary[]
  selectedId: number
  currentId: number | null
  onRestore: (id: number) => void
  onClose: () => void
}) {
  const idx = versions.findIndex((v) => v.id === selectedId)
  const summary = versions[idx]
  const previousId = versions[idx - 1]?.id ?? null
  const isCurrent = selectedId === currentId
  const [against, setAgainst] = useState<Against>(isCurrent ? 'previous' : 'current')
  const compareId = against === 'previous' || isCurrent ? previousId : currentId

  const selected = useDraft(selectedId)
  const compare = useDraft(compareId)
  const parts = useMemo(
    () =>
      selected.data && (compareId === null || compare.data)
        ? diffWords(compare.data?.content ?? '', selected.data.content)
        : null,
    [selected.data, compare.data, compareId],
  )

  if (!summary) return null
  const stats = parts && compareId !== null ? diffStats(parts) : null
  const compareVersion = versions.find((v) => v.id === compareId)?.version

  return (
    <section aria-label={`Versjon ${summary.version}`} data-testid="version-view" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold">
          Versjon {summary.version}
          <span className="text-muted-foreground font-normal">
            {' '}
            · {authorLabel(summary)} · {fmtVersionTime(summary.created_at)}
          </span>
        </h2>
        <div className="ml-auto flex items-center gap-1">
          {!isCurrent && (
            <Button size="sm" variant="outline" onClick={() => onRestore(selectedId)}>
              <RotateCcw /> Gjenopprett
            </Button>
          )}
          <Button size="icon-sm" variant="ghost" aria-label="Lukk versjonen" onClick={onClose}>
            <X />
          </Button>
        </div>
      </div>
      {summary.instruction && <p className="text-muted-foreground text-sm">Instruksjon: «{summary.instruction}»</p>}
      {!isCurrent && previousId !== null && (
        <Segmented<Against>
          label="Sammenlign med"
          value={against}
          onChange={setAgainst}
          options={[
            { value: 'previous', label: 'Mot forrige' },
            { value: 'current', label: 'Mot gjeldende' },
          ]}
          className="self-start"
        />
      )}
      {stats && (
        <p className="text-muted-foreground text-xs" data-testid="diff-stats">
          Mot versjon {compareVersion}: <span className="text-good">+{stats.added}</span>{' '}
          <span className="text-bad">−{stats.removed}</span> ord
        </p>
      )}
      {parts ? (
        <DiffText parts={parts} />
      ) : (
        <Skeleton className="h-64 w-full" />
      )}
    </section>
  )
}
