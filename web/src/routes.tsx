import { createBrowserRouter, type RouteObject } from 'react-router'
import { AppShell } from '@/components/AppShell'
import { JobsRoute } from '@/features/jobs/JobsPage'
import { OverviewPage } from '@/features/overview/OverviewPage'

/**
 * Routes (FRONTEND §4.2). Same routes on mobile and PC.
 * The daily loop (Oversikt, Jobber) is in the main bundle; the other screens load on first
 * visit so the first paint on the phone stays small (FRONTEND §8, F5).
 */
export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    hydrateFallbackElement: null,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'jobber', element: <JobsRoute /> },
      { path: 'jobber/:id', element: <JobsRoute /> },
      {
        path: 'tracker',
        lazy: () => import('@/features/tracker/TrackerPage').then((m) => ({ Component: m.TrackerPage })),
      },
      {
        path: 'soknader',
        lazy: () =>
          import('@/features/drafts/ApplicationsPage').then((m) => ({ Component: m.ApplicationsPage })),
      },
      {
        path: 'soknader/:applicationId',
        lazy: () => import('@/features/drafts/EditorPage').then((m) => ({ Component: m.EditorPage })),
      },
      {
        path: 'profil/*',
        lazy: () => import('@/features/profile/ProfilePage').then((m) => ({ Component: m.ProfilePage })),
      },
      {
        path: 'innstillinger',
        lazy: () => import('@/features/settings/SettingsPage').then((m) => ({ Component: m.SettingsPage })),
      },
      {
        path: 'logg',
        lazy: () => import('@/features/logs/LogsPage').then((m) => ({ Component: m.LogsPage })),
      },
      {
        path: 'mer',
        lazy: () => import('@/features/more/MorePage').then((m) => ({ Component: m.MorePage })),
      },
      {
        path: '*',
        lazy: () => import('@/features/NotFoundPage').then((m) => ({ Component: m.NotFoundPage })),
      },
    ],
  },
]

export const createRouter = () => createBrowserRouter(routes)
