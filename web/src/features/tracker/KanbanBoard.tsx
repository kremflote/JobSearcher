import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import { ChevronsLeft, ChevronsRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { ApplicationCard, ApplicationStatus } from '@/api/types'
import { Sheet } from '@/components/Sheet'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'
import { STATUS_LABEL, TRACKER_COLUMNS, type TrackerColumn } from '@/lib/status'
import { cn } from '@/lib/utils'
import { groupByColumn, legalTargets } from './cards'
import { StatusMenu, TrackerCardBody } from './TrackerCard'
import { useMove } from './useMove'

type Move = (card: ApplicationCard, to: ApplicationStatus) => void

/**
 * Kanban on PC (FRONTEND §5.4). Drag a card to a column (only legal columns light up), or use
 * the card's status menu. A drop on "Avsluttet" with more than one legal status asks which.
 */
export function KanbanBoard({ cards, onOpen }: { cards: ApplicationCard[]; onOpen: (id: number) => void }) {
  const move = useMove()
  const toast = useToast()
  const groups = useMemo(() => groupByColumn(cards), [cards])
  const [dragging, setDragging] = useState<ApplicationCard | null>(null)
  const [choice, setChoice] = useState<{ card: ApplicationCard; targets: ApplicationStatus[] } | null>(null)
  const [showClosed, setShowClosed] = useState(false)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }))

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    setDragging(null)
    const card = cards.find((c) => c.id === active.id)
    const column = TRACKER_COLUMNS.find((c) => c.id === over?.id)
    if (!card || !column || column.statuses.includes(card.status)) return
    const targets = legalTargets(card, column)
    if (targets.length === 1) move(card, targets[0]!)
    else if (targets.length > 1) setChoice({ card, targets })
    else toast({ message: `Kan ikke flytte fra ${STATUS_LABEL[card.status]} til ${column.label}.` })
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={({ active }) => setDragging(cards.find((c) => c.id === active.id) ?? null)}
      onDragEnd={onDragEnd}
      onDragCancel={() => setDragging(null)}
    >
      <div className="flex h-[calc(100dvh-3rem)] gap-3 overflow-x-auto p-3" data-testid="kanban">
        {groups.map(({ column, cards }) => (
          <Column
            key={column.id}
            column={column}
            cards={cards}
            dragging={dragging}
            collapsed={column.id === 'avsluttet' && !showClosed}
            onToggle={column.id === 'avsluttet' ? () => setShowClosed((v) => !v) : undefined}
            onOpen={onOpen}
            onMove={move}
          />
        ))}
      </div>
      <DragOverlay dropAnimation={null}>
        {dragging && (
          <div className="bg-card w-60 rotate-1 rounded-md border p-2.5 shadow-lg">
            <TrackerCardBody card={dragging} />
          </div>
        )}
      </DragOverlay>
      <Sheet open={!!choice} onOpenChange={(o) => !o && setChoice(null)} title={`Avslutt: ${choice?.card.job_title ?? ''}`}>
        <div className="flex flex-col gap-2">
          {choice?.targets.map((s) => (
            <Button
              key={s}
              variant="outline"
              onClick={() => {
                move(choice.card, s)
                setChoice(null)
              }}
            >
              {STATUS_LABEL[s]}
            </Button>
          ))}
        </div>
      </Sheet>
    </DndContext>
  )
}

function Column({
  column,
  cards,
  dragging,
  collapsed,
  onToggle,
  onOpen,
  onMove,
}: {
  column: TrackerColumn
  cards: ApplicationCard[]
  dragging: ApplicationCard | null
  collapsed: boolean
  onToggle?: () => void
  onOpen: (id: number) => void
  onMove: Move
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id })
  const home = !!dragging && column.statuses.includes(dragging.status)
  const legal = !!dragging && !home && legalTargets(dragging, column).length > 0

  return (
    <section
      ref={setNodeRef}
      aria-label={column.label}
      data-testid={`column-${column.id}`}
      data-legal={dragging ? String(legal) : undefined}
      className={cn(
        'bg-muted/40 flex min-h-0 flex-col rounded-lg border transition-[opacity,box-shadow]',
        collapsed ? 'w-12 shrink-0' : 'min-w-56 flex-1',
        dragging && !legal && !home && 'opacity-40',
        legal && 'ring-primary/30 ring-2',
        legal && isOver && 'ring-primary bg-accent',
      )}
    >
      {collapsed ? (
        <button
          type="button"
          onClick={onToggle}
          className="text-muted-foreground hover:text-foreground flex flex-1 flex-col items-center gap-2 py-3 text-sm"
          aria-label={`Vis ${column.label} (${cards.length})`}
        >
          <ChevronsRight className="size-4" aria-hidden />
          <span className="font-medium [writing-mode:vertical-rl]">
            {column.label} · {cards.length}
          </span>
        </button>
      ) : (
        <>
          <header className="flex h-10 shrink-0 items-center gap-2 px-3 text-sm font-medium">
            {column.label}
            <span className="text-muted-foreground text-xs tabular-nums">{cards.length}</span>
            {onToggle && (
              <Button size="icon-sm" variant="ghost" className="ml-auto" aria-label={`Skjul ${column.label}`} onClick={onToggle}>
                <ChevronsLeft />
              </Button>
            )}
          </header>
          <ul className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-2 pb-2">
            {cards.map((card) => (
              <DraggableCard key={card.id} card={card} onOpen={onOpen} onMove={onMove} />
            ))}
            {!cards.length && <li className="text-muted-foreground px-1 py-4 text-center text-xs">Tom</li>}
          </ul>
        </>
      )}
    </section>
  )
}

function DraggableCard({ card, onOpen, onMove }: { card: ApplicationCard; onOpen: (id: number) => void; onMove: Move }) {
  const { setNodeRef, listeners, isDragging } = useDraggable({ id: card.id })
  return (
    <li
      ref={setNodeRef}
      {...listeners}
      data-testid="tracker-card"
      data-app-id={card.id}
      data-status={card.status}
      className={cn(
        'bg-card hover:border-foreground/20 relative cursor-grab touch-none rounded-md border p-2.5 shadow-xs',
        isDragging && 'opacity-30',
      )}
    >
      <button
        type="button"
        onClick={() => onOpen(card.id)}
        aria-label={`Åpne ${card.job_title}`}
        className="focus-visible:ring-ring absolute inset-0 rounded-md outline-none focus-visible:ring-2"
      />
      <div className="pointer-events-none relative [&_button]:pointer-events-auto">
        <TrackerCardBody card={card} menu={<StatusMenu card={card} onMove={(s) => onMove(card, s)} />} />
      </div>
    </li>
  )
}
