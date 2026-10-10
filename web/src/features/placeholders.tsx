/**
 * F0 placeholder screens. Each is replaced by its feature folder in the wave noted
 * (FRONTEND §5 and §8).
 */
import { useParams } from 'react-router'
import { useJobCount, useOverview } from '@/api/queries'
import { ComingSoon, Page } from '@/components/Page'
import { Skeleton } from '@/components/ui/skeleton'

export function OverviewPage() {
  const { data, isPending, isError } = useOverview()
  return (
    <Page title="Oversikt">
      <ComingSoon wave="F1">
        <div className="mt-2" data-testid="overview-summary">
          {isPending ? (
            <Skeleton className="h-4 w-48" />
          ) : isError ? (
            'Fikk ikke kontakt med API-et.'
          ) : (
            `${data.deadlines.length} frister de neste 14 dagene, ${data.new_since_last.top.length} nye topp-jobber.`
          )}
        </div>
      </ComingSoon>
    </Page>
  )
}

export function JobsPage() {
  const { data: total, isPending, isError } = useJobCount()
  return (
    <Page title="Jobber">
      <ComingSoon wave="F1">
        <div className="mt-2" data-testid="job-count">
          {isPending ? <Skeleton className="h-4 w-32" /> : isError ? 'Fikk ikke kontakt med API-et.' : `${total} jobber`}
        </div>
      </ComingSoon>
    </Page>
  )
}

export function JobDetailPage() {
  const { id } = useParams()
  return (
    <Page title={`Jobb ${id}`}>
      <ComingSoon wave="F1" />
    </Page>
  )
}

export function TrackerPage() {
  return (
    <Page title="Tracker">
      <ComingSoon wave="F2" />
    </Page>
  )
}

export function ApplicationsPage() {
  return (
    <Page title="Søknader">
      <ComingSoon wave="F3" />
    </Page>
  )
}

export function EditorPage() {
  const { applicationId } = useParams()
  return (
    <Page title={`Søknad ${applicationId}`}>
      <ComingSoon wave="F3" />
    </Page>
  )
}

export function ProfilePage() {
  return (
    <Page title="Profil">
      <ComingSoon wave="F4" />
    </Page>
  )
}

export function SettingsPage() {
  return (
    <Page title="Innstillinger">
      <ComingSoon wave="F4" />
    </Page>
  )
}

export function LogsPage() {
  return (
    <Page title="Logg">
      <ComingSoon wave="F4" />
    </Page>
  )
}

export function NotFoundPage() {
  return (
    <Page title="Fant ikke siden">
      <p className="text-muted-foreground text-sm">Denne adressen finnes ikke.</p>
    </Page>
  )
}
