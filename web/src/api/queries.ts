import { QueryClient, useQuery } from '@tanstack/react-query'
import { api, ApiError, unwrap } from './client'

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

export function useJobCount() {
  return useQuery({
    queryKey: ['jobs', 'count'],
    queryFn: () => unwrap(api.GET('/api/jobs', { params: { query: { limit: 1 } } })),
    select: (list) => list.total,
  })
}
