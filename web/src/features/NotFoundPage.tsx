import { Page } from '@/components/Page'

export function NotFoundPage() {
  return (
    <Page title="Fant ikke siden">
      <p className="text-muted-foreground text-sm">Denne adressen finnes ikke.</p>
    </Page>
  )
}
