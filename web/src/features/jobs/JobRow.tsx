import { Check, X } from 'lucide-react'
import { forwardRef } from 'react'
import { Link } from 'react-router'
import type { TriageStatus } from '@/api/queries'
import type { JobListItem } from '@/api/types'
import { DeadlineBadge, ScoreBadge, StatusBadge, Tag } from '@/components/badges'
import { cn } from '@/lib/utils'
import { canTriage } from './useTriage'
import { useSwipe } from './useSwipe'

type Props = {
  job: JobListItem
  href: string
  /** Selected with j/k or open in the detail pane. */
  active: boolean
  /** Triaged out of the current filter: stays in place, dimmed, until the list reloads. */
  dimmed: boolean
  swipe: boolean
  onTriage: (status: TriageStatus) => void
  onSelect: () => void
}

/** One job in the list (FRONTEND §5.2). Swipe right = Interessant, left = Ikke aktuell. */
export const JobRow = forwardRef<HTMLLIElement, Props>(function JobRow(
  { job, href, active, dimmed, swipe, onTriage, onSelect },
  ref,
) {
  const swipeable = swipe && canTriage(job.status)
  const { offset, dragging, handlers } = useSwipe(
    (dir) => onTriage(dir === 'right' ? 'interessant' : 'ikke_aktuell'),
    swipeable,
  )
  const right = offset > 0

  return (
    <li ref={ref} className="relative overflow-hidden" data-job-id={job.id} data-status={job.status}>
      {offset !== 0 && (
        <div
          aria-hidden
          className={cn(
            'absolute inset-0 flex items-center px-4 text-sm font-medium',
            right ? 'bg-good-soft text-good justify-start' : 'bg-muted text-muted-foreground justify-end',
          )}
        >
          {right ? <Check className="mr-1.5 size-4" /> : null}
          {right ? 'Interessant' : 'Ikke aktuell'}
          {!right ? <X className="ml-1.5 size-4" /> : null}
        </div>
      )}
      <Link
        to={href}
        state={{ fromList: true }}
        draggable={false}
        onClick={onSelect}
        aria-current={active ? 'true' : undefined}
        style={{
          transform: offset ? `translateX(${offset}px)` : undefined,
          transition: dragging ? 'none' : 'transform 150ms ease-out',
          opacity: dragging ? Math.max(0.6, 1 - Math.abs(offset) / 800) : undefined,
        }}
        className={cn(
          'bg-background relative flex min-h-11 touch-pan-y flex-col justify-center gap-0.5 px-3 py-2 select-none md:min-h-9 md:py-1.5',
          'hover:bg-accent/50 focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none focus-visible:ring-inset',
          active && 'bg-accent',
          dimmed && 'opacity-50',
        )}
        {...handlers}
      >
        <div className="flex items-center gap-2">
          <span className="min-w-0 flex-1 truncate text-sm font-medium">{job.title}</span>
          <ScoreBadge score={job.score} />
        </div>
        <div className="text-muted-foreground flex items-center gap-1.5 text-xs">
          <span className="min-w-0 truncate">
            {job.company}
            {job.location_text && ` · ${job.location_text}`}
          </span>
          <span className="ml-auto flex shrink-0 items-center gap-1">
            {job.is_new && <Tag tone="good" title="Ny siden forrige kjøring">Ny</Tag>}
            {job.reposted && <Tag>Lagt ut på nytt</Tag>}
            {job.ad_text_status === 'missing' && <Tag tone="muted">Bare tittel kjent</Tag>}
            <StatusBadge status={job.status} />
            <DeadlineBadge deadline={job.deadline} deadlineText={job.deadline_text} />
          </span>
        </div>
      </Link>
    </li>
  )
})

