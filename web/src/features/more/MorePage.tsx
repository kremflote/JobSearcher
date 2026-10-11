import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import { useOverview } from '@/api/queries'
import { IS_MOCK, MockBadge } from '@/components/AppShell'
import { MORE_ITEMS } from '@/components/nav'
import { Page } from '@/components/Page'
import { ThemeMenu } from '@/components/ThemeMenu'
import { LlmUsageCard } from '@/features/overview/LlmUsageCard'
import { SourcesCard } from '@/features/overview/OverviewPage'

/** "Mer" on mobile (FRONTEND §4.2): the remaining pages, source status with "Kjør nå", and LLM usage. */
export function MorePage() {
  const { data } = useOverview()
  return (
    <Page title="Mer" actions={IS_MOCK && <MockBadge />}>
      <ul className="bg-card divide-y rounded-lg border">
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
      <div className="mt-4 flex flex-col gap-4">
        {data && <SourcesCard sources={data.sources} lastRunAt={data.last_run_at} />}
        <LlmUsageCard />
      </div>
      <div className="mt-4 flex items-center justify-between rounded-lg border px-3 py-1.5 text-sm">
        Utseende
        <ThemeMenu />
      </div>
    </Page>
  )
}
