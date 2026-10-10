import { NavLink, Outlet, ScrollRestoration, useLocation } from 'react-router'
import { cn } from '@/lib/utils'
import { MORE_PATHS, NAV_ITEMS, TAB_ITEMS } from './nav'
import { TaskIndicator } from './tasks'
import { ThemeMenu } from './ThemeMenu'
import { ToastProvider } from './Toaster'

export const IS_MOCK = import.meta.env.VITE_MOCK === '1'

/**
 * Layout (FRONTEND §4.1): bottom tabs < 768 px, icon sidebar 768–1023 px, sidebar with text ≥ 1024 px.
 */
export function AppShell() {
  return (
    <ToastProvider>
      <div className="min-h-dvh md:flex">
        <Sidebar />
        <main className="min-w-0 flex-1 pb-[calc(3.5rem+env(safe-area-inset-bottom))] md:pb-0">
          <TaskIndicator />
          <Outlet />
        </main>
        <BottomTabs />
      </div>
      <ScrollRestoration />
    </ToastProvider>
  )
}

function Sidebar() {
  return (
    <nav
      aria-label="Hovedmeny"
      className="bg-sidebar text-sidebar-foreground border-sidebar-border sticky top-0 hidden h-dvh shrink-0 flex-col border-r md:flex md:w-14 lg:w-52"
    >
      <div className="flex h-12 items-center gap-2 px-3 lg:px-4">
        <img src="/icon.svg" alt="" className="size-7 shrink-0 rounded-md" />
        <span className="hidden font-semibold lg:inline">Jobbsøk</span>
        {IS_MOCK && <MockBadge className="ml-auto hidden lg:inline-flex" />}
      </div>
      <ul className="flex flex-1 flex-col gap-0.5 px-2 py-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === '/'}
              title={label}
              className={({ isActive }) =>
                cn(
                  'flex h-9 items-center gap-3 rounded-md px-2.5 text-sm transition-colors',
                  'hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                  'focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-2',
                  'md:justify-center lg:justify-start',
                  isActive ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium' : 'text-muted-foreground',
                )
              }
            >
              <Icon className="size-4 shrink-0" aria-hidden />
              <span className="md:sr-only lg:not-sr-only">{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="flex items-center justify-center p-2 lg:justify-start">
        <ThemeMenu />
      </div>
    </nav>
  )
}

function BottomTabs() {
  const { pathname } = useLocation()
  const inMore = MORE_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))

  return (
    <nav
      aria-label="Hovedmeny"
      className="bg-background/95 fixed inset-x-0 bottom-0 z-40 border-t pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
    >
      <ul className="grid h-14 grid-cols-4">
        {TAB_ITEMS.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex h-full flex-col items-center justify-center gap-0.5 text-[11px]',
                  (to === '/mer' ? inMore : isActive) ? 'text-foreground font-medium' : 'text-muted-foreground',
                )
              }
            >
              <Icon className="size-5" aria-hidden />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export function MockBadge({ className }: { className?: string }) {
  return (
    <span
      title="Data kommer fra oppdiktede fixtures (MSW)"
      className={cn('bg-warn-soft text-warn rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide', className)}
    >
      MOCK
    </span>
  )
}
