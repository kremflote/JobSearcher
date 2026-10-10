import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** Page frame with a sticky title bar. */
export function Page({
  title,
  actions,
  children,
  className,
}: {
  title: string
  actions?: ReactNode
  children?: ReactNode
  className?: string
}) {
  return (
    <div className="flex min-h-full flex-col">
      <header className="bg-background/95 sticky top-0 z-30 flex h-12 items-center gap-2 border-b px-4 backdrop-blur">
        <h1 className="truncate text-base font-semibold">{title}</h1>
        <div className="ml-auto flex items-center gap-1">{actions}</div>
      </header>
      <div className={cn('flex-1 p-4', className)}>{children}</div>
    </div>
  )
}

/** Placeholder body for screens that arrive in a later wave (FRONTEND §8). */
export function ComingSoon({ wave, children }: { wave: string; children?: ReactNode }) {
  return (
    <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
      <p>
        Kommer i bølge <span className="text-foreground font-medium">{wave}</span>.
      </p>
      {children}
    </div>
  )
}
