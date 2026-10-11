import { ChevronRight, Trash2 } from 'lucide-react'
import { Link } from 'react-router'
import { ApiError } from '@/api/client'
import { useApplications, useDeleteDrafts } from '@/api/queries'
import type { ApplicationCard } from '@/api/types'
import { DeadlineBadge, StatusBadge } from '@/components/badges'
import { Page } from '@/components/Page'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { StartDraftButton } from './StartDraftButton'
import { fmtVersionTime } from './Versions'

const BEFORE_APPLYING = ['interessant', 'utkast']

/**
 * `/soknader` (FRONTEND §5.5): applications with drafts, last edited first, and interesting jobs
 * without a draft yet, each with "Lag søknadsutkast".
 */
export function ApplicationsPage() {
  const apps = useApplications()
  const deleteDrafts = useDeleteDrafts()
  const toast = useToast()
  const onDelete = (c: ApplicationCard) => {
    if (!window.confirm(`Slette søknadsutkastet til ${c.company}? Alle versjoner og chatten forsvinner.`)) return
    deleteDrafts.mutate(c.id, {
      onSuccess: () => toast({ message: `Utkast slettet: ${c.job_title}` }),
      onError: (e) => toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke slette utkastet.' }),
    })
  }
  const cards = apps.data?.items ?? []
  const withDrafts = cards
    .filter((c) => c.latest_draft_id !== null)
    .sort((a, b) => (a.latest_draft_at! < b.latest_draft_at! ? 1 : -1))
  const waiting = cards
    .filter((c) => c.status === 'interessant' && c.latest_draft_id === null)
    .sort((a, b) => (a.deadline ?? '9999').localeCompare(b.deadline ?? '9999'))

  return (
    <Page title="Søknader">
      {apps.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : apps.isError ? (
        <div className="text-sm">
          <p className="text-muted-foreground mb-2">Kunne ikke hente søknadene.</p>
          <Button size="sm" variant="outline" onClick={() => apps.refetch()}>
            Prøv igjen
          </Button>
        </div>
      ) : (
        <div className="mx-auto flex max-w-3xl flex-col gap-6">
          <section aria-labelledby="drafts-heading">
            <h2 id="drafts-heading" className="mb-2 text-sm font-semibold">
              Utkast
            </h2>
            {withDrafts.length ? (
              <ul className="divide-y rounded-lg border" data-testid="draft-list">
                {withDrafts.map((c) => (
                  <li key={c.id} className="hover:bg-muted/50 flex items-center pr-1">
                    <Link to={`/soknader/${c.id}`} className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2.5">
                      <Summary card={c} />
                      <span className="text-muted-foreground hidden shrink-0 text-xs sm:inline">
                        Endret {fmtVersionTime(c.latest_draft_at!)}
                      </span>
                      <ChevronRight className="text-muted-foreground size-4 shrink-0" aria-hidden />
                    </Link>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      className="text-muted-foreground hover:text-destructive shrink-0"
                      aria-label={`Slett utkastet til ${c.job_title}`}
                      title="Slett utkast"
                      disabled={deleteDrafts.isPending && deleteDrafts.variables === c.id}
                      onClick={() => onDelete(c)}
                    >
                      <Trash2 />
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
                Ingen søknadsutkast ennå. Lag et fra en jobb du har merket som interessant.
              </p>
            )}
          </section>

          {waiting.length > 0 && (
            <section aria-labelledby="waiting-heading">
              <h2 id="waiting-heading" className="mb-2 text-sm font-semibold">
                Interessant, uten utkast
              </h2>
              <ul className="divide-y rounded-lg border" data-testid="waiting-list">
                {waiting.map((c) => (
                  <li key={c.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                    <Summary card={c} />
                    <StartDraftButton jobId={c.job_id} size="xs" />
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </Page>
  )
}

function Summary({ card }: { card: ApplicationCard }) {
  return (
    <span className="min-w-0 flex-1">
      <span className="block truncate text-sm font-medium">{card.job_title}</span>
      <span className="text-muted-foreground flex items-center gap-2 text-xs">
        <span className="truncate">{card.company}</span>
        <StatusBadge status={card.status} />
        {BEFORE_APPLYING.includes(card.status) && <DeadlineBadge deadline={card.deadline} />}
      </span>
    </span>
  )
}
