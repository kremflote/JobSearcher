import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** Bordered card with a title row, used on Oversikt and Mer. */
export function Card({
  title,
  action,
  children,
  className,
  testId,
  onClick,
}: {
  title: string
  action?: ReactNode
  children: ReactNode
  className?: string
  testId?: string
  /** Makes the whole card clickable; give keyboard users a button in `action` as well. */
  onClick?: () => void
}) {
  return (
    <section className={cn('bg-card flex flex-col rounded-lg border', className)} data-testid={testId} onClick={onClick}>
      <header className="flex h-10 items-center gap-2 border-b px-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        <div className="ml-auto flex items-center gap-1">{action}</div>
      </header>
      {children}
    </section>
  )
}
