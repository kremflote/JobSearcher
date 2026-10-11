import { useQueryClient } from '@tanstack/react-query'
import { format, parseISO } from 'date-fns'
import { nb } from 'date-fns/locale'
import { ExternalLink, FileText, Loader2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { ApiError } from '@/api/client'
import { updateApplication, useApplicationEvents } from '@/api/queries'
import type { ApplicationCard, ApplicationPatch } from '@/api/types'
import { DeadlineBadge, StatusBadge } from '@/components/badges'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'
import { STATUS_LABEL } from '@/lib/status'
import { cn } from '@/lib/utils'
import { useMove } from './useMove'

const FIELD =
  'border-input bg-background focus-visible:ring-ring w-full rounded-md border px-3 py-2 text-base outline-none focus-visible:ring-2 md:text-sm'

const EDITABLE = ['next_step', 'next_step_at', 'follow_up_at', 'notes'] as const
type Form = Record<(typeof EDITABLE)[number], string>

const toForm = (c: ApplicationCard): Form => ({
  next_step: c.next_step ?? '',
  next_step_at: c.next_step_at ?? '',
  follow_up_at: c.follow_up_at ?? '',
  notes: c.notes ?? '',
})

const fmtAt = (iso: string) => format(parseISO(iso), "d. MMM yyyy 'kl.' HH:mm", { locale: nb })

/**
 * Side panel (PC) / full-screen sheet (mobile) for one application (FRONTEND §5.4): status
 * moves, next step with date, follow-up, notes and the event log. Saves only changed fields.
 */
export function ApplicationPanel({ card }: { card: ApplicationCard }) {
  const qc = useQueryClient()
  const toast = useToast()
  const move = useMove()
  const events = useApplicationEvents(card.id)
  const [form, setForm] = useState<Form>(() => toForm(card))
  const [saving, setSaving] = useState(false)

  const saved = toForm(card)
  const changed = EDITABLE.filter((k) => form[k].trim() !== saved[k])
  const set = (k: keyof Form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const save = async () => {
    const patch: ApplicationPatch = Object.fromEntries(changed.map((k) => [k, form[k].trim() || null]))
    setSaving(true)
    try {
      await updateApplication(qc, card.id, patch)
      toast({ message: 'Lagret' })
    } catch (e) {
      toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke lagre.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      className="flex min-h-[calc(100%-3rem)] flex-col"
      onSubmit={(e) => {
        e.preventDefault()
        if (changed.length) save()
      }}
      data-testid="application-panel"
    >
      <div className="flex flex-1 flex-col gap-5 p-4">
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted-foreground">{card.company}</span>
            <StatusBadge status={card.status} />
            <DeadlineBadge deadline={card.deadline} />
          </div>
          {card.applied_at && <p className="text-muted-foreground text-xs">Søkt {fmtAt(card.applied_at)}</p>}
          <Link
            to={`/jobber/${card.job_id}`}
            state={{ fromList: true }}
            className="text-primary inline-flex w-fit items-center gap-1 text-sm underline-offset-4 hover:underline"
          >
            <ExternalLink className="size-3.5" aria-hidden /> Åpne jobben
          </Link>
          {card.latest_draft_id && (
            <Link
              to={`/soknader/${card.id}`}
              className="text-primary inline-flex w-fit items-center gap-1 text-sm underline-offset-4 hover:underline"
            >
              <FileText className="size-3.5" aria-hidden /> Åpne søknadsutkastet
            </Link>
          )}
        </div>

        {card.allowed_next.length > 0 && (
          <Section title="Flytt til">
            <div className="flex flex-wrap gap-2">
              {card.allowed_next.map((s) => (
                <Button key={s} type="button" size="sm" variant="outline" onClick={() => move(card, s)}>
                  {STATUS_LABEL[s]}
                </Button>
              ))}
            </div>
          </Section>
        )}

        <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
          <Field label="Neste steg">
            <input className={FIELD} value={form.next_step} onChange={set('next_step')} placeholder="F.eks. Intervju 2. runde" />
          </Field>
          <Field label="Dato">
            <input type="date" className={FIELD} value={form.next_step_at} onChange={set('next_step_at')} />
          </Field>
          <Field label="Følg opp">
            <input type="date" className={FIELD} value={form.follow_up_at} onChange={set('follow_up_at')} />
          </Field>
        </div>
        <Field label="Notater">
          <textarea className={cn(FIELD, 'min-h-28 resize-y')} rows={5} value={form.notes} onChange={set('notes')} />
        </Field>

        <Section title="Hendelser">
          {events.isPending ? (
            <p className="text-muted-foreground text-sm">Henter …</p>
          ) : (
            <ol className="flex flex-col gap-2" data-testid="event-log">
              {[...(events.data ?? [])].reverse().map((e) => (
                <li key={e.id} className="border-l-2 pl-3 text-sm">
                  <div>
                    {e.from_status ? `${STATUS_LABEL[e.from_status]} → ` : ''}
                    <span className="font-medium">{STATUS_LABEL[e.to_status]}</span>
                  </div>
                  <div className="text-muted-foreground text-xs">{fmtAt(e.at)}</div>
                  {e.comment && <p className="mt-0.5 text-xs">{e.comment}</p>}
                </li>
              ))}
            </ol>
          )}
        </Section>
      </div>

      <div
        className="bg-background sticky bottom-0 flex items-center justify-end gap-2 border-t px-4 py-3"
      >
        {changed.length > 0 && (
          <Button type="button" variant="ghost" onClick={() => setForm(saved)}>
            Forkast
          </Button>
        )}
        <Button type="submit" disabled={!changed.length || saving}>
          {saving && <Loader2 className="animate-spin" />}
          Lagre
        </Button>
      </div>
    </form>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="text-muted-foreground mb-2 text-xs font-medium tracking-wide uppercase">{title}</h3>
      {children}
    </section>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-muted-foreground text-xs font-medium">{label}</span>
      {children}
    </label>
  )
}
