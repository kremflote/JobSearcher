import { createBrowserRouter, type RouteObject } from 'react-router'
import { AppShell } from '@/components/AppShell'
import { MorePage } from '@/features/more/MorePage'
import {
  ApplicationsPage,
  EditorPage,
  JobDetailPage,
  JobsPage,
  LogsPage,
  NotFoundPage,
  OverviewPage,
  ProfilePage,
  SettingsPage,
  TrackerPage,
} from '@/features/placeholders'

/** Routes (FRONTEND §4.2). Same routes on mobile and PC. */
export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'jobber', element: <JobsPage /> },
      { path: 'jobber/:id', element: <JobDetailPage /> },
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
