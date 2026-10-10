import { ChevronDown, ExternalLink, PencilLine } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import type { ApplicationCard } from '@/api/types'
import { Sheet } from '@/components/Sheet'
import { Button } from '@/components/ui/button'
import { STATUS_LABEL } from '@/lib/status'
import { cn } from '@/lib/utils'
import { groupByColumn } from './cards'
import { TrackerCardBody } from './TrackerCard'
import { useMove } from './useMove'

/**
 * Tracker below 1024 px (FRONTEND §5.4): list grouped by status with collapsible groups and
 * status chips (`?vis=<column>`). Tapping a card opens an action sheet with the legal next statuses.
 */
export function TrackerList({ cards, onOpen }: { cards: ApplicationCard[]; onOpen: (id: number) => void }) {
  const [params, setParams] = useSearchParams()
  const shown = params.get('vis')
  const groups = useMemo(() => groupByColumn(cards), [cards])
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({ avsluttet: true })
  const [actionId, setActionId] = useState<number | null>(null)
  const action = cards.find((c) => c.id === actionId) ?? null
  const move = useMove()

  const setShown = (id: string | null) =>
    setParams(
      (p) => {
        if (id) p.set('vis', id)
        else p.delete('vis')
        return p
      },
      { replace: true },
    )

  return (
    <>
      <div role="group" aria-label="Status" className="flex gap-1.5 overflow-x-auto border-b px-3 py-2 [scrollbar-width:none]">
        <Chip active={!shown} onClick={() => setShown(null)}>
          Alle
        </Chip>
        {groups.map(({ column, cards }) => (
          <Chip key={column.id} active={shown === column.id} onClick={() => setShown(shown === column.id ? null : column.id)}>
            {column.label} <span className="tabular-nums opacity-70">{cards.length}</span>
          </Chip>
        ))}
      </div>

      {groups
        .filter(({ column }) => !shown || shown === column.id)
        .map(({ column, cards }) => {
          const open = shown === column.id || !collapsed[column.id]
          return (
            <section key={column.id} aria-label={column.label} data-testid={`group-${column.id}`}>
              <h2>
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => setCollapsed((c) => ({ ...c, [column.id]: open }))}
                  className="bg-muted/50 flex h-10 w-full items-center gap-2 border-b px-4 text-sm font-medium"
                >
                  {column.label}
                  <span className="text-muted-foreground text-xs tabular-nums">{cards.length}</span>
                  <ChevronDown className={cn('ml-auto size-4 transition-transform', !open && '-rotate-90')} aria-hidden />
                </button>
              </h2>
              {open && (
                <ul className="divide-y border-b">
                  {cards.map((card) => (
                    <li key={card.id} data-testid="tracker-card" data-app-id={card.id} data-status={card.status}>
                      <button
                        type="button"
                        onClick={() => setActionId(card.id)}
                        className="active:bg-accent w-full px-4 py-2.5"
                        aria-label={card.job_title}
                      >
                        <TrackerCardBody card={card} />
                      </button>
                    </li>
                  ))}
                  {!cards.length && <li className="text-muted-foreground px-4 py-3 text-xs">Ingen søknader her.</li>}
                </ul>
              )}
            </section>
          )
        })}

      <Sheet open={!!action} onOpenChange={(o) => !o && setActionId(null)} title={action?.job_title ?? ''}>
        {action && (
          <div className="flex flex-col gap-3" data-testid="action-sheet">
            <p className="text-muted-foreground -mt-2 text-sm">
              {action.company} · {STATUS_LABEL[action.status]}
            </p>
            {action.allowed_next.length > 0 && (
              <div>
                <h3 className="text-muted-foreground mb-1.5 text-xs font-medium">Flytt til</h3>
                <div className="grid grid-cols-2 gap-2">
                  {action.allowed_next.map((s) => (
                    <Button
                      key={s}
                      variant="outline"
                      className="h-11"
                      onClick={() => {
                        move(action, s)
                        setActionId(null)
                      }}
                    >
                      {STATUS_LABEL[s]}
                    </Button>
                  ))}
                </div>
              </div>
            )}
            <div className="flex flex-col gap-1 border-t pt-2">
              <Button
                variant="ghost"
                className="h-11 justify-start"
                onClick={() => {
                  setActionId(null)
                  onOpen(action.id)
                }}
              >
                <PencilLine /> Neste steg, oppfølging og notater
              </Button>
              <Button variant="ghost" className="h-11 justify-start" asChild>
                <Link to={`/jobber/${action.job_id}`} state={{ fromList: true }}>
                  <ExternalLink /> Åpne jobben
                </Link>
              </Button>
            </div>
          </div>
        )}
      </Sheet>
    </>
  )
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        'flex h-8 shrink-0 items-center gap-1 rounded-full border px-3 text-sm whitespace-nowrap',
        active ? 'bg-primary text-primary-foreground border-primary' : 'bg-background',
      )}
    >
      {children}
    </button>
  )
}
