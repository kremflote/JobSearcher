import { X } from 'lucide-react'
import { Dialog } from 'radix-ui'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Side = 'bottom' | 'right' | 'full'

const SIDE_CLASS: Record<Side, string> = {
  bottom:
    'data-[state=open]:slide-in-from-bottom inset-x-0 bottom-0 max-h-[85dvh] rounded-t-xl border-t px-4 pt-2 pb-[calc(1rem+env(safe-area-inset-bottom))]',
  right: 'data-[state=open]:slide-in-from-right inset-y-0 right-0 w-full max-w-md border-l',
  full: 'data-[state=open]:slide-in-from-bottom inset-0 pb-[env(safe-area-inset-bottom)]',
}

/**
 * Modal sheet (FRONTEND §4.1): `bottom` is the action sheet for choices on mobile, `right` the
 * side panel on PC, `full` the full-screen editor on mobile. `right` and `full` get a header
 * with a close button.
 */
export function Sheet({
  open,
  onOpenChange,
  title,
  side = 'bottom',
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  side?: Side
  children: ReactNode
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="data-[state=open]:animate-in data-[state=open]:fade-in fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content
          aria-describedby={undefined}
          className={cn(
            'bg-background data-[state=open]:animate-in fixed z-50 overflow-y-auto outline-none',
            SIDE_CLASS[side],
          )}
        >
          {side === 'bottom' ? (
            <>
              <div className="bg-muted mx-auto mb-3 h-1 w-10 rounded-full" aria-hidden />
              <Dialog.Title className="mb-3 text-base font-semibold">{title}</Dialog.Title>
              {children}
            </>
          ) : (
            <>
              <div className="bg-background/95 sticky top-0 z-10 flex h-12 items-center gap-2 border-b px-4 backdrop-blur">
                <Dialog.Title className="min-w-0 flex-1 truncate text-base font-semibold">{title}</Dialog.Title>
                <Dialog.Close asChild>
                  <Button size="icon-sm" variant="ghost" aria-label="Lukk">
                    <X />
                  </Button>
                </Dialog.Close>
              </div>
              {children}
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
