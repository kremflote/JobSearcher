import { useSearchParams } from 'react-router'
import { useApplications } from '@/api/queries'
import { Page } from '@/components/Page'
import { Sheet } from '@/components/Sheet'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { CLOSED_STATUSES } from '@/lib/status'
import { useIsWide } from '@/lib/useMediaQuery'
import { ApplicationPanel } from './ApplicationPanel'
import { KanbanBoard } from './KanbanBoard'
import { TrackerList } from './TrackerList'

/**
 * `/tracker` (FRONTEND §5.4): kanban ≥ 1024 px, grouped list below. `?app=<id>` opens the
 * application panel (side panel on PC, full screen on mobile), so Back closes it.
 */
export function TrackerPage() {
  const wide = useIsWide()
  const apps = useApplications()
  const [params, setParams] = useSearchParams()
  const openId = Number(params.get('app')) || null
  const cards = apps.data?.items ?? []
  const open = cards.find((c) => c.id === openId) ?? null
  const active = cards.filter((c) => !CLOSED_STATUSES.includes(c.status)).length

  const setOpen = (id: number | null) =>
    setParams((p) => {
      if (id) p.set('app', String(id))
      else p.delete('app')
      return p
    })

  return (
    <Page
      title="Tracker"
      className="p-0"
      actions={
        apps.data && (
          <span className="text-muted-foreground text-xs tabular-nums" data-testid="active-count">
            {active} aktive
          </span>
        )
      }
    >
      {apps.isPending ? (
        <div className="flex flex-col gap-3 p-4" aria-busy="true">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : apps.isError ? (
        <div className="p-4 text-sm">
          <p className="text-muted-foreground mb-2">Kunne ikke hente søknadene.</p>
          <Button size="sm" variant="outline" onClick={() => apps.refetch()}>
            Prøv igjen
          </Button>
        </div>
      ) : wide ? (
        <KanbanBoard cards={cards} onOpen={setOpen} />
      ) : (
        <TrackerList cards={cards} onOpen={setOpen} />
      )}

      <Sheet open={!!open} onOpenChange={(o) => !o && setOpen(null)} title={open?.job_title ?? ''} side={wide ? 'right' : 'full'}>
        {open && <ApplicationPanel key={open.id} card={open} />}
      </Sheet>
    </Page>
  )
}
