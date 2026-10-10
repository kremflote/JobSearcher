import createClient from 'openapi-fetch'
import type { paths } from './schema'

/** Typed API client. Paths include the `/api` prefix, e.g. `api.GET('/api/jobs')`. */
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  // Look up fetch per call so MSW's interception in tests (installed later) is used.
  fetch: (request) => globalThis.fetch(request),
})

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message)
  }
}

/** Unwraps an openapi-fetch result for TanStack Query: returns data or throws ApiError. */
export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await promise
  if (error !== undefined || data === undefined) {
    const e = (error ?? {}) as { detail?: unknown; code?: unknown }
    const detail = typeof e.detail === 'string' ? e.detail : response.statusText
    throw new ApiError(response.status, typeof e.code === 'string' ? e.code : 'unknown', detail)
  }
  return data
}
