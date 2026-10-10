import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { ApiError } from '@/api/client'
import { updateApplication } from '@/api/queries'
import type { ApplicationCard, ApplicationStatus } from '@/api/types'
import { useToast } from '@/components/Toaster'
import { STATUS_LABEL } from '@/lib/status'

/**
 * Moves an application to a new status with an undo toast (FRONTEND §5.4). Undo PATCHes back to
 * the previous status, which the backend treats as removing the event, and restores the
 * follow-up date that a move to `sokt` sets.
 */
export function useMove() {
  const qc = useQueryClient()
  const toast = useToast()
  const fail = useCallback(
    (e: unknown) => toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke endre status.' }),
    [toast],
  )

  return useCallback(
    (card: ApplicationCard, to: ApplicationStatus) => {
      if (card.status === to || !card.allowed_next.includes(to)) return
      updateApplication(qc, card.id, { status: to }).then(() => {
        toast({
          message: `${STATUS_LABEL[to]}: ${card.job_title}`,
          action: {
            label: 'Angre',
            onClick: () =>
              updateApplication(qc, card.id, { status: card.status, follow_up_at: card.follow_up_at }).then(
                () => toast({ message: `Angret: ${card.job_title}` }),
                fail,
              ),
          },
        })
      }, fail)
    },
    [qc, toast, fail],
  )
}
