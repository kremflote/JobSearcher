import {
  QueryClient,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query'
import { useEffect } from 'react'
import { api, ApiError, unwrap } from './client'
import type { paths } from './schema'
import type { ApplicationCard, ApplicationList, ApplicationPatch, JobDetail, JobList, Task } from './types'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
  },
})

export function useOverview() {
  return useQuery({
    queryKey: ['overview'],
    queryFn: () => unwrap(api.GET('/api/overview')),
  })
}

// --- Jobs ---------------------------------------------------------------------

export type JobQuery = Omit<NonNullable<paths['/api/jobs']['get']['parameters']['query']>, 'cursor' | 'limit'>
export type TriageStatus = paths['/api/jobs/{job_id}/status']['put']['requestBody']['content']['application/json']['status']

export const JOB_PAGE_SIZE = 25

/** Job list with cursor paging (FRONTEND §5.2). No refetch on focus, so the list doesn't jump mid-triage. */
export function useJobs(query: JobQuery) {
  return useInfiniteQuery({
    queryKey: ['jobs', 'list', query],
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET('/api/jobs', {
          params: { query: { ...query, cursor: pageParam ?? undefined, limit: JOB_PAGE_SIZE } },
        }),
      ),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    refetchOnWindowFocus: false,
  })
}

export function useJob(id: number | null) {
  return useQuery({
    queryKey: ['jobs', 'detail', id],
    queryFn: () => unwrap(api.GET('/api/jobs/{job_id}', { params: { path: { job_id: id! } } })),
    enabled: id !== null,
  })
}

/**
 * Triage (PUT /api/jobs/{id}/status). Patches cached lists in place instead of refetching, so the
 * row stays put (dimmed) until the list is loaded again (FRONTEND §5.2). A plain promise rather
 * than `useMutation`, so it completes (and can be undone) after the caller has unmounted.
 */
export async function setJobStatus(qc: QueryClient, id: number, status: TriageStatus) {
  const res = await unwrap(api.PUT('/api/jobs/{job_id}/status', { params: { path: { job_id: id } }, body: { status } }))
  qc.setQueriesData<InfiniteData<JobList>>({ queryKey: ['jobs', 'list'] }, (data) =>
    data && {
      ...data,
      pages: data.pages.map((p) => ({
        ...p,
        items: p.items.map((j) => (j.id === res.job_id ? { ...j, status: res.status } : j)),
      })),
    },
  )
  qc.setQueryData<JobDetail>(['jobs', 'detail', res.job_id], (job) =>
    job && {
      ...job,
      status: res.status,
      application: res.application_id
        ? { id: res.application_id, status: res.status, latest_draft_id: job.application?.latest_draft_id ?? null }
        : null,
    },
  )
  qc.invalidateQueries({ queryKey: ['overview'] })
  qc.invalidateQueries({ queryKey: ['applications'] })
  return res
}

// --- Applications (tracker, FRONTEND §5.4) ---------------------------------------

export function useApplications() {
  return useQuery({
    queryKey: ['applications', 'list'],
    queryFn: () => unwrap(api.GET('/api/applications')),
  })
}

export function useApplicationEvents(id: number | null) {
  return useQuery({
    queryKey: ['applications', 'events', id],
    queryFn: () =>
      unwrap(api.GET('/api/applications/{application_id}/events', { params: { path: { application_id: id! } } })),
    enabled: id !== null,
  })
}

const patchCards = (qc: QueryClient, fn: (a: ApplicationCard) => ApplicationCard) =>
  qc.setQueryData<ApplicationList>(['applications', 'list'], (data) => data && { items: data.items.map(fn) })

const PATCH_FIELDS = ['next_step', 'next_step_at', 'follow_up_at', 'notes'] as const

/** Optimistic version of the server's update; moves are disabled until the real card arrives. */
const applyPatch = (a: ApplicationCard, p: ApplicationPatch): ApplicationCard => ({
  ...a,
  ...Object.fromEntries(PATCH_FIELDS.filter((k) => k in p).map((k) => [k, p[k] ?? null])),
  ...(p.status ? { status: p.status, allowed_next: [] } : {}),
})

/**
 * PATCH /api/applications/{id}. Applied to the cached list first, so a dropped card stays where it
 * landed; rolled back by refetching if the server refuses (409 on an illegal transition).
 * A plain promise like `setJobStatus`, so the undo toast still works after the panel closes.
 */
export async function updateApplication(qc: QueryClient, id: number, patch: ApplicationPatch) {
  await qc.cancelQueries({ queryKey: ['applications', 'list'] })
  patchCards(qc, (a) => (a.id === id ? applyPatch(a, patch) : a))
  try {
    const card = await unwrap(
      api.PATCH('/api/applications/{application_id}', { params: { path: { application_id: id } }, body: patch }),
    )
    patchCards(qc, (a) => (a.id === id ? card : a))
    return card
  } catch (e) {
    qc.invalidateQueries({ queryKey: ['applications', 'list'] })
    throw e
  } finally {
    qc.invalidateQueries({ queryKey: ['applications', 'events', id] })
    if (patch.status) {
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['overview'] })
    } else if (PATCH_FIELDS.some((k) => k !== 'notes' && k in patch)) {
      qc.invalidateQueries({ queryKey: ['overview'] })
    }
  }
}

// --- Background tasks (FRONTEND §3.3) -------------------------------------------

const TERMINAL: readonly Task['status'][] = ['done', 'failed', 'cancelled']
export const isTaskActive = (t: Task) => !TERMINAL.includes(t.status)

/** Queries a finished task of each kind may have changed. */
const AFFECTS: Record<Task['kind'], string[][]> = {
  run: [['overview'], ['jobs'], ['logs']],
  draft: [['jobs'], ['applications'], ['drafts']],
  research: [['jobs']],
  revise: [['drafts']],
  rescore: [['jobs'], ['overview']],
  distill: [['profile']],
}

export function useActiveTasks() {
  return useQuery({
    queryKey: ['tasks', 'active'],
    queryFn: () => unwrap(api.GET('/api/tasks', { params: { query: { active: true } } })),
    refetchInterval: (q) => (q.state.data?.length ? 2000 : false),
  })
}

/** Polls one task every 2 s until it is done, failed or cancelled, then invalidates what it touched. */
export function useTask(id: string | null) {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: ['tasks', 'detail', id],
    queryFn: () => unwrap(api.GET('/api/tasks/{task_id}', { params: { path: { task_id: id! } } })),
    enabled: id !== null,
    refetchInterval: (q) => (q.state.data && !isTaskActive(q.state.data) ? false : 2000),
  })
  const task = query.data
  const finished = task && !isTaskActive(task)
  useEffect(() => {
    if (!task || !finished) return
    for (const key of AFFECTS[task.kind]) qc.invalidateQueries({ queryKey: key })
    qc.invalidateQueries({ queryKey: ['tasks', 'active'] })
  }, [qc, task?.id, task?.kind, finished]) // eslint-disable-line react-hooks/exhaustive-deps
  return query
}

/** "Kjør nå" (POST /api/runs). */
export function useStartRun() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => unwrap(api.POST('/api/runs')),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks', 'active'] }),
  })
}

export function useCancelTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => unwrap(api.POST('/api/tasks/{task_id}/cancel', { params: { path: { task_id: id } } })),
    onSuccess: (task) => {
      qc.setQueryData(['tasks', 'detail', task.id], task)
      qc.invalidateQueries({ queryKey: ['tasks', 'active'] })
    },
  })
}
