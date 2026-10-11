import { cn } from '@/lib/utils'
import type { DiffPart } from './diff'

/** Word diff: added green, removed red and struck through (FRONTEND §5.5, also used in Profil). */
export function DiffText({ parts, className }: { parts: DiffPart[]; className?: string }) {
  return (
    <div className={cn('rounded-lg border p-3 text-sm leading-relaxed whitespace-pre-wrap', className)} data-testid="diff">
      {parts.map((p, i) =>
        p.kind === 'same' ? (
          <span key={i}>{p.text}</span>
        ) : (
          <span
            key={i}
            className={cn('rounded-sm', p.kind === 'added' ? 'bg-good-soft text-good' : 'bg-bad-soft text-bad line-through')}
            data-diff={p.kind}
          >
            {p.text}
          </span>
        ),
      )}
    </div>
  )
}
