/**
 * F0 placeholder screens. Each is replaced by its feature folder in the wave noted
 * (FRONTEND §5 and §8).
 */
import { useParams } from 'react-router'
import { ComingSoon, Page } from '@/components/Page'

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
