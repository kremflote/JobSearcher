import {
  Briefcase,
  Ellipsis,
  FileText,
  LayoutDashboard,
  ScrollText,
  Settings,
  SquareKanban,
  UserRound,
  type LucideIcon,
} from 'lucide-react'

export type NavItem = { to: string; label: string; icon: LucideIcon }

/** Sidebar on PC (FRONTEND §4.2). */
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Oversikt', icon: LayoutDashboard },
  { to: '/jobber', label: 'Jobber', icon: Briefcase },
  { to: '/tracker', label: 'Tracker', icon: SquareKanban },
  { to: '/soknader', label: 'Søknader', icon: FileText },
  { to: '/profil', label: 'Profil', icon: UserRound },
  { to: '/innstillinger', label: 'Innstillinger', icon: Settings },
  { to: '/logg', label: 'Logg', icon: ScrollText },
]

/** Bottom tabs on mobile. The rest of NAV_ITEMS is reached through "Mer". */
export const TAB_ITEMS: NavItem[] = [
  ...NAV_ITEMS.slice(0, 3),
  { to: '/mer', label: 'Mer', icon: Ellipsis },
]

export const MORE_ITEMS: NavItem[] = NAV_ITEMS.slice(3)

/** Routes that light up the "Mer" tab. */
export const MORE_PATHS = ['/mer', ...MORE_ITEMS.map((i) => i.to)]
