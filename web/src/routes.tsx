import { createBrowserRouter, type RouteObject } from 'react-router'
import { AppShell } from '@/components/AppShell'
import { JobsRoute } from '@/features/jobs/JobsPage'
import { MorePage } from '@/features/more/MorePage'
import { OverviewPage } from '@/features/overview/OverviewPage'
import { TrackerPage } from '@/features/tracker/TrackerPage'
import { ApplicationsPage } from '@/features/drafts/ApplicationsPage'
import { EditorPage } from '@/features/drafts/EditorPage'
import { LogsPage } from '@/features/logs/LogsPage'
import { NotFoundPage } from '@/features/NotFoundPage'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { SettingsPage } from '@/features/settings/SettingsPage'

/** Routes (FRONTEND §4.2). Same routes on mobile and PC. */
export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'jobber', element: <JobsRoute /> },
      { path: 'jobber/:id', element: <JobsRoute /> },
      { path: 'tracker', element: <TrackerPage /> },
      { path: 'soknader', element: <ApplicationsPage /> },
      { path: 'soknader/:applicationId', element: <EditorPage /> },
      { path: 'profil/*', element: <ProfilePage /> },
      { path: 'innstillinger', element: <SettingsPage /> },
      { path: 'logg', element: <LogsPage /> },
      { path: 'mer', element: <MorePage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const createRouter = () => createBrowserRouter(routes)
