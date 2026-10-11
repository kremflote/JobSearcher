import { Loader2, Play } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { ApiError } from '@/api/client'
import { isTaskActive, useActiveTasks, useCancelTask, useStartRun, useTask } from '@/api/queries'
import type { Task } from '@/api/types'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const KIND_LABEL: Record<Task['kind'], string> = {
  run: 'Kjøring',
  draft: 'Søknadsutkast',
  research: 'Research',
  revise: 'Revisjon',
  rescore: 'Ny scoring',
  distill: 'Destillering',
}

/**
 * Active background tasks (FRONTEND §3.3): top of the content on PC, above the bottom tabs on
 * mobile. Each task seen as active is watched with `useTask` until it finishes, even after it
 * has left the active list, so the affected queries are always invalidated.
 */
export function TaskIndicator() {
  const { data: active } = useActiveTasks()
  const [watched, setWatched] = useState<string[]>([])

  useEffect(() => {
    if (!active?.length) return
    setWatched((w) => {
      const add = active.map((t) => t.id).filter((id) => !w.includes(id))
      return add.length ? [...w, ...add] : w
    })
  }, [active])

  if (!watched.length) return null
  return (
    <div
      className={cn(
        'above-action-bar z-40 flex flex-col gap-1 px-3 py-1.5 empty:hidden',
        'fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] md:static',
        'bg-background/95 border-t backdrop-blur md:border-t-0 md:border-b',
      )}
      data-testid="task-indicator"
    >
      {watched.map((id) => (
        <TaskRow key={id} id={id} onFinished={() => setWatched((w) => w.filter((x) => x !== id))} />
      ))}
    </div>
  )
}

function TaskRow({ id, onFinished }: { id: string; onFinished: () => void }) {
  const { data: task, isError } = useTask(id)
  const cancel = useCancelTask()
  const toast = useToast()
  const navigate = useNavigate()
  const done = isError || (task && !isTaskActive(task))

  useEffect(() => {
    if (!done) return
    if (task) {
      const label = KIND_LABEL[task.kind]
      const msg =
        task.status === 'done'
          ? `${label} ferdig${task.message ? `: ${task.message.replace(/^Ferdig:?\s*/, '')}` : ''}`
          : task.status === 'cancelled'
            ? `${label} avbrutt`
            : `${label} feilet${task.message ? `: ${task.message}` : ''}`
      const appId = task.status === 'done' && task.kind === 'draft' ? task.result?.application_id : null
      toast({ message: msg, action: appId ? { label: 'Åpne', onClick: () => navigate(`/soknader/${appId}`) } : undefined })
    }
    onFinished()
  }, [done]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!task || done) return null
  const pct = task.progress === null ? null : Math.round(task.progress * 100)
  return (
    <div className="flex items-center gap-2 text-sm" role="status">
      <Loader2 className="text-muted-foreground size-4 animate-spin" aria-hidden />
      <span className="font-medium">{KIND_LABEL[task.kind]}</span>
      <span className="text-muted-foreground min-w-0 flex-1 truncate">
        {task.message}
        {pct !== null && ` · ${pct} %`}
      </span>
      <Button size="xs" variant="ghost" onClick={() => cancel.mutate(task.id)} disabled={cancel.isPending}>
        Avbryt
      </Button>
    </div>
  )
}

/** "Kjør nå" (POST /api/runs). Disabled while a run is active. */
export function RunNowButton({ className }: { className?: string }) {
  const start = useStartRun()
  const { data: active } = useActiveTasks()
  const toast = useToast()
  const running = start.isPending || !!active?.some((t) => t.kind === 'run')
  return (
    <Button
      size="sm"
      variant="outline"
      className={className}
      disabled={running}
      onClick={() =>
        start.mutate(undefined, {
          onError: (e) => toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke starte kjøringen.' }),
        })
      }
    >
      {running ? <Loader2 className="animate-spin" /> : <Play />}
      {running ? 'Kjører …' : 'Kjør nå'}
    </Button>
  )
}
