import { Loader2, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { ApiError } from '@/api/client'
import { isTaskActive, useRescoreEstimate, useStartRescore, useTask } from '@/api/queries'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const usd = (n: number) => `$${n.toFixed(n < 0.1 ? 3 : 2)}`

/**
 * "Score på nytt" (ARCHITECTURE §5.5): how many active jobs were scored with an older profile or
 * prompt, the estimated cost, and a button that starts the rescore task. Never automatic.
 */
export function RescoreCard({ className, hideWhenNone = false }: { className?: string; hideWhenNone?: boolean }) {
  const toast = useToast()
  const estimate = useRescoreEstimate()
  const start = useStartRescore()
  const [taskId, setTaskId] = useState<string | null>(null)
  const task = useTask(taskId)
  const busy = start.isPending || (taskId !== null && (!task.data || isTaskActive(task.data)))
  const n = estimate.data?.stale_jobs ?? 0

  if (!estimate.data || (hideWhenNone && n === 0 && !busy)) return null

  return (
    <div className={cn('flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2.5 text-sm', className)} data-testid="rescore-card">
      <p className="min-w-0 flex-1">
        {busy ? (
          <>Scorer jobbene på nytt …</>
        ) : n === 0 ? (
          <span className="text-muted-foreground">Alle aktive jobber er scoret med gjeldende profil og prompt.</span>
        ) : (
          <>
            <span className="font-medium">{n} aktive jobber</span> er scoret med gammel profil eller prompt. Estimert
            kostnad {usd(estimate.data.estimated_cost_usd)}.
          </>
        )}
      </p>
      {(n > 0 || busy) && (
        <Button
          size="sm"
          variant="secondary"
          disabled={busy}
          onClick={() =>
            start.mutate(undefined, {
              onSuccess: (r) => setTaskId(r.task_id),
              onError: (e) => toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke starte scoringen.' }),
            })
          }
        >
          {busy ? <Loader2 className="animate-spin" /> : <RefreshCw />}
          Score på nytt
        </Button>
      )}
    </div>
  )
}
