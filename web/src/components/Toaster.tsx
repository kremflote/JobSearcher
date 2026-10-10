import { X } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'

type ToastAction = { label: string; onClick: () => void }
type ToastInput = { message: string; action?: ToastAction; duration?: number }
type Toast = ToastInput & { id: number }

const ToastContext = createContext<((t: ToastInput) => void) | null>(null)

/** Default lifetime; the triage undo toast lives 5 s (FRONTEND §2). */
export const TOAST_MS = 5000

/** One toast at a time: a new one replaces the old (the latest triage is the one to undo). */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null)
  const nextId = useRef(1)
  const show = useCallback((t: ToastInput) => setToast({ ...t, id: nextId.current++ }), [])

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), toast.duration ?? TOAST_MS)
    return () => clearTimeout(timer)
  }, [toast])

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div
        aria-live="polite"
        className="above-action-bar pointer-events-none fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-50 flex justify-center px-3 md:inset-x-auto md:right-4 md:bottom-4"
      >
        {toast && (
          <div
            key={toast.id}
            role="status"
            className="bg-popover text-popover-foreground animate-in fade-in slide-in-from-bottom-2 pointer-events-auto flex w-full max-w-sm items-center gap-2 rounded-lg border py-1.5 pr-1.5 pl-3 text-sm shadow-lg"
          >
            <span className="min-w-0 flex-1 truncate">{toast.message}</span>
            {toast.action && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  toast.action!.onClick()
                  setToast(null)
                }}
              >
                {toast.action.label}
              </Button>
            )}
            <Button size="icon-sm" variant="ghost" aria-label="Lukk" onClick={() => setToast(null)}>
              <X />
            </Button>
          </div>
        )}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}
