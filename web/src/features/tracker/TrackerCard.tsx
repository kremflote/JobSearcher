import { ArrowRight, BellRing, EllipsisVertical, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ApplicationCard, ApplicationStatus } from '@/api/types'
import { DeadlineBadge, StatusBadge } from '@/components/badges'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { shortDate } from '@/lib/format'
import { CLOSED_STATUSES, STATUS_LABEL } from '@/lib/status'
import { cn } from '@/lib/utils'

function DateText({ iso }: { iso: string }) {
  const d = shortDate(iso)
  return <span className={cn('tabular-nums', d.overdue && 'text-bad font-medium')}>{d.text}</span>
}

/**
 * Card content (FRONTEND §5.4): title, company, deadline, next step + date, follow-up, contact.
 * The caller supplies the clickable wrapper; `menu` sits above it.
 */
export function TrackerCardBody({ card, menu }: { card: ApplicationCard; menu?: ReactNode }) {
  const beforeApplying = card.status === 'interessant' || card.status === 'utkast'
  return (
    <div className="flex flex-col gap-1 text-left">
      <div className="flex items-start gap-1">
        <div className="min-w-0 flex-1">
          <div className="line-clamp-2 text-sm leading-snug font-medium">{card.job_title}</div>
          <div className="text-muted-foreground truncate text-xs">{card.company}</div>
        </div>
        {menu}
      </div>
      {card.next_step && (
        <div className="flex items-center gap-1 text-xs">
          <ArrowRight className="text-muted-foreground size-3 shrink-0" aria-hidden />
          <span className="min-w-0 truncate">{card.next_step}</span>
          {card.next_step_at && (
            <>
              <span className="text-muted-foreground">·</span>
              <DateText iso={card.next_step_at} />
            </>
          )}
        </div>
      )}
      {card.follow_up_at && !CLOSED_STATUSES.includes(card.status) && (
        <div className="flex items-center gap-1 text-xs">
          <BellRing className="text-muted-foreground size-3 shrink-0" aria-hidden />
          <span>Følg opp</span>
          <DateText iso={card.follow_up_at} />
        </div>
      )}
      {(beforeApplying || card.contact_name || CLOSED_STATUSES.includes(card.status)) && (
        <div className="flex items-center gap-1.5 text-xs">
          {CLOSED_STATUSES.includes(card.status) && <StatusBadge status={card.status} />}
          {beforeApplying && <DeadlineBadge deadline={card.deadline} />}
          {card.contact_name && (
            <span className="text-muted-foreground flex min-w-0 items-center gap-1">
              <UserRound className="size-3 shrink-0" aria-hidden />
              <span className="truncate">{card.contact_name}</span>
            </span>
          )}
        </div>
      )}
    </div>
  )
}

/** Status menu on the card: the keyboard/no-drag way to move it (FRONTEND §6, accessibility). */
export function StatusMenu({
  card,
  onMove,
}: {
  card: ApplicationCard
  onMove: (to: ApplicationStatus) => void
}) {
  if (!card.allowed_next.length) return null
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label={`Flytt ${card.job_title}`}
          className="relative z-10 -mt-1 -mr-1 size-7"
          onPointerDown={(e) => e.stopPropagation()}
        >
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Flytt til</DropdownMenuLabel>
        {card.allowed_next.map((s) => (
          <DropdownMenuItem key={s} onSelect={() => onMove(s)}>
            {STATUS_LABEL[s]}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
