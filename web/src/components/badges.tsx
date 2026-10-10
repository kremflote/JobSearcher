import type { ReactNode } from 'react'
import type { ApplicationStatus } from '@/api/types'
import { deadlineInfo, scoreTone, type Tone } from '@/lib/format'
import { STATUS_CLASS, STATUS_LABEL } from '@/lib/status'
import { cn } from '@/lib/utils'

export const TONE_CLASS: Record<Tone, string> = {
  good: 'bg-good-soft text-good',
  warn: 'bg-warn-soft text-warn',
  bad: 'bg-bad-soft text-bad',
  neutral: 'bg-secondary text-secondary-foreground',
  muted: 'text-muted-foreground',
}

const PILL = 'inline-flex h-5 shrink-0 items-center rounded px-1.5 text-xs font-medium tabular-nums whitespace-nowrap'

/** Score (FRONTEND §6): always the number, colour only as a hint. */
export function ScoreBadge({ score, className }: { score: number | null; className?: string }) {
  if (score === null)
    return (
      <span className={cn(PILL, TONE_CLASS.muted, className)} title="Ikke scoret">
        –
      </span>
    )
  return (
    <span className={cn(PILL, 'min-w-7 justify-center', TONE_CLASS[scoreTone(score)], className)} title={`Score ${score}`}>
      {score}
    </span>
  )
}

/** Deadline as relative text with the date in the tooltip (FRONTEND §6). */
export function DeadlineBadge({
  deadline,
  deadlineText,
  className,
}: {
  deadline: string | null
  deadlineText?: string | null
  className?: string
}) {
  const d = deadlineInfo(deadline, deadlineText)
  return (
    <span className={cn(PILL, TONE_CLASS[d.tone], className)} title={d.date ? `Frist ${d.date}` : 'Ukjent frist'}>
      {d.relative}
    </span>
  )
}

export function StatusBadge({ status, className }: { status: ApplicationStatus; className?: string }) {
  return <span className={cn(PILL, STATUS_CLASS[status], className)}>{STATUS_LABEL[status]}</span>
}

/** Neutral tag, same shape as the other pills: Ny (since last run), Lagt ut på nytt, Bare tittel kjent. */
export function Tag({
  children,
  tone = 'neutral',
  title,
  className,
}: {
  children: ReactNode
  tone?: Tone
  title?: string
  className?: string
}) {
  return (
    <span className={cn(PILL, TONE_CLASS[tone], className)} title={title}>
      {children}
    </span>
  )
}
