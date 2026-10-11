import { AlertTriangle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

const key = (applicationId: number) => `jobsearcher.claims.${applicationId}`

function load(applicationId: number): string[] {
  try {
    const raw = localStorage.getItem(key(applicationId))
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

/**
 * `claims_to_verify` as yellow warnings that can be ticked off (FRONTEND §5.5). What is ticked is
 * a per-browser convenience, kept in localStorage per application and claim text.
 */
export function ClaimsBar({ applicationId, claims }: { applicationId: number; claims: string[] }) {
  const [checked, setChecked] = useState<string[]>(() => load(applicationId))

  useEffect(() => {
    try {
      localStorage.setItem(key(applicationId), JSON.stringify(checked))
    } catch {
      // Storage blocked: ticks just don't survive a reload.
    }
  }, [applicationId, checked])

  if (!claims.length) return null
  const open = claims.filter((c) => !checked.includes(c)).length
  return (
    <section
      aria-label="Påstander å sjekke"
      data-testid="claims"
      className={cn('rounded-lg border px-3 py-2 text-sm', open ? 'border-warn/40 bg-warn-soft' : 'bg-muted/40')}
    >
      <p className={cn('mb-1 flex items-center gap-1.5 font-medium', open ? 'text-warn' : 'text-muted-foreground')}>
        <AlertTriangle className="size-4" aria-hidden />
        {open ? `Sjekk ${open} ${open === 1 ? 'påstand' : 'påstander'} før du sender` : 'Alle påstander er sjekket'}
      </p>
      <ul className="flex flex-col gap-1">
        {claims.map((claim) => {
          const done = checked.includes(claim)
          return (
            <li key={claim}>
              <label className="flex cursor-pointer items-start gap-2">
                <input
                  type="checkbox"
                  className="accent-primary mt-0.5 size-4 shrink-0"
                  checked={done}
                  onChange={() => setChecked((c) => (done ? c.filter((x) => x !== claim) : [...c, claim]))}
                />
                <span className={cn(done && 'text-muted-foreground line-through')}>{claim}</span>
              </label>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
