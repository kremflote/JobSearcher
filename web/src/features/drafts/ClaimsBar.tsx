import { AlertTriangle, Check, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Verdict = 'ok' | 'wrong'

const key = (applicationId: number) => `jobsearcher.claims.${applicationId}`

function load(applicationId: number): Record<string, Verdict> {
  try {
    const raw = localStorage.getItem(key(applicationId))
    if (!raw) return {}
    const parsed = JSON.parse(raw) as string[] | Record<string, Verdict>
    // Older entries were a list of ticked claims.
    return Array.isArray(parsed) ? Object.fromEntries(parsed.map((c) => [c, 'ok' as const])) : parsed
  } catch {
    return {}
  }
}

/** The instruction "Stemmer ikke" sends to the revision agent. */
export const rejectInstruction = (claim: string) =>
  `Denne påstanden stemmer ikke: «${claim}». Fjern den fra brevet, eller skriv om avsnittet uten den. Ikke erstatt den med en annen påstand som ikke står i profilen.`

/**
 * `claims_to_verify` as yellow warnings (FRONTEND §5.5). "Stemmer" marks a claim as checked;
 * "Stemmer ikke" asks the revision agent to take it out. What was marked is a per-browser
 * convenience, kept in localStorage per application and claim text.
 */
export function ClaimsBar({
  applicationId,
  claims,
  onReject,
  disabled,
}: {
  applicationId: number
  claims: string[]
  onReject: (claim: string) => void
  disabled: boolean
}) {
  const [verdicts, setVerdicts] = useState<Record<string, Verdict>>(() => load(applicationId))

  useEffect(() => {
    try {
      localStorage.setItem(key(applicationId), JSON.stringify(verdicts))
    } catch {
      // Storage blocked: marks just don't survive a reload.
    }
  }, [applicationId, verdicts])

  if (!claims.length) return null
  const set = (claim: string, v: Verdict | null) =>
    setVerdicts(({ [claim]: _, ...rest }) => (v ? { ...rest, [claim]: v } : rest))
  const open = claims.filter((c) => !verdicts[c]).length
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
          const v = verdicts[claim]
          return (
            <li key={claim} className="flex items-start gap-2">
              <span className={cn('flex-1', v === 'ok' && 'text-muted-foreground line-through')}>
                {claim}
                {v === 'wrong' && <span className="text-muted-foreground"> · sendt til agenten</span>}
              </span>
              {v ? (
                <Button size="sm" variant="ghost" className="h-6 px-2 text-xs" onClick={() => set(claim, null)}>
                  Angre
                </Button>
              ) : (
                <span className="flex shrink-0 gap-1">
                  <Button size="sm" variant="outline" className="h-6 px-2 text-xs" onClick={() => set(claim, 'ok')}>
                    <Check className="size-3" /> Stemmer
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 px-2 text-xs"
                    disabled={disabled}
                    onClick={() => {
                      set(claim, 'wrong')
                      onReject(claim)
                    }}
                  >
                    <X className="size-3" /> Stemmer ikke
                  </Button>
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
