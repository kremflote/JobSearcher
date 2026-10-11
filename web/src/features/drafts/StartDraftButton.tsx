import { useQueryClient } from '@tanstack/react-query'
import { FileText, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { ApiError } from '@/api/client'
import { isTaskActive, useStartDraft, useTask } from '@/api/queries'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'

/**
 * "Lag søknadsutkast" (FRONTEND §5.3): starts research + writer as a background task. When it
 * finishes, the job and application queries refetch and the caller shows "Åpne søknad" instead;
 * the task toast links to the editor.
 */
export function StartDraftButton({ jobId, size = 'sm' }: { jobId: number; size?: 'sm' | 'xs' }) {
  const qc = useQueryClient()
  const toast = useToast()
  const start = useStartDraft()
  const [taskId, setTaskId] = useState<string | null>(null)
  const task = useTask(taskId)
  const busy = start.isPending || (taskId !== null && (!task.data || isTaskActive(task.data)))

  const onClick = () =>
    start.mutate(jobId, {
      onSuccess: (r) => setTaskId(r.task_id),
      onError: (e) => {
        if (e instanceof ApiError && e.code === 'draft_exists') {
          qc.invalidateQueries({ queryKey: ['jobs'] })
          qc.invalidateQueries({ queryKey: ['applications'] })
        }
        toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke starte utkastet.' })
      },
    })

  return (
    <Button size={size} variant="secondary" disabled={busy} onClick={onClick}>
      {busy ? <Loader2 className="animate-spin" /> : <FileText />}
      {busy ? 'Skriver utkast …' : 'Lag søknadsutkast'}
    </Button>
  )
}
