import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import { IS_MOCK, MockBadge } from '@/components/AppShell'
import { MORE_ITEMS } from '@/components/nav'
import { Page } from '@/components/Page'
import { ThemeMenu } from '@/components/ThemeMenu'

/** "Mer" on mobile (FRONTEND §4.2). Last-run status and "Kjør nå" arrive in F1. */
export function MorePage() {
  return (
    <Page title="Mer" actions={IS_MOCK && <MockBadge />}>
      <ul className="divide-y rounded-lg border">
        {MORE_ITEMS.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <Link to={to} className="flex h-11 items-center gap-3 px-3 text-sm">
              <Icon className="text-muted-foreground size-4" aria-hidden />
              {label}
              <ChevronRight className="text-muted-foreground ml-auto size-4" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex items-center justify-between rounded-lg border px-3 py-1.5 text-sm">
        Utseende
        <ThemeMenu />
      </div>
    </Page>
  )
}
