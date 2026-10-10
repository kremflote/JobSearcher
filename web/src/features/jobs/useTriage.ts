import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { ApiError } from '@/api/client'
import { setJobStatus, type TriageStatus } from '@/api/queries'
import type { ApplicationStatus, JobListItem } from '@/api/types'
import { useToast } from '@/components/Toaster'
import { STATUS_LABEL } from '@/lib/status'

/** Statuses triage can move between; later ones are changed in the tracker (ARCHITECTURE §9.1). */
export const TRIAGE_STATUSES: readonly ApplicationStatus[] = ['ny', 'interessant', 'ikke_aktuell']
export const canTriage = (status: ApplicationStatus) => TRIAGE_STATUSES.includes(status)

type Undo = { id: number; title: string; prev: TriageStatus }

/** Shared by the list and the mobile detail screen, so `u` also undoes a triage made in the detail. */
const undoStack: Undo[] = []

/**
 * Triage with an undo toast (5 s) and an undo stack for the `u` key (FRONTEND §5.2).
 * `onUndo` gets the job id so the list can move the selection back to it.
 */
export function useTriage(onUndo?: (id: number) => void) {
  const qc = useQueryClient()
  const toast = useToast()

  const fail = useCallback(
    (e: unknown) => toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke endre status.' }),
    [toast],
  )

  const undo = useCallback(() => {
    const last = undoStack.pop()
    if (!last) return false
    setJobStatus(qc, last.id, last.prev).then(() => toast({ message: `Angret: ${last.title}` }), fail)
    onUndo?.(last.id)
    return true
  }, [qc, toast, fail, onUndo])

  const triage = useCallback(
    (job: Pick<JobListItem, 'id' | 'title' | 'status'>, status: TriageStatus) => {
      if (!canTriage(job.status) || job.status === status) return false
      const entry: Undo = { id: job.id, title: job.title, prev: job.status as TriageStatus }
      setJobStatus(qc, job.id, status).then(() => {
        undoStack.push(entry)
        toast({ message: `${STATUS_LABEL[status]}: ${job.title}`, action: { label: 'Angre', onClick: undo } })
      }, fail)
      return true
    },
    [qc, toast, fail, undo],
  )

  return { triage, undo }
}
