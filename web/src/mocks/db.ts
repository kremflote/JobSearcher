/** In-memory mock database built from the invented fixtures. Rebuilt on every page load. */
import type { JobDetail, JobListItem, Task } from '@/api/types'
import { buildApplications } from './fixtures/applications'
import { buildJobs } from './fixtures/jobs'
import {
  buildAgentRuns,
  buildDiscarded,
  buildProfileFiles,
  buildRuns,
  buildSettings,
  buildSourceStatus,
} from './fixtures/system'
import type { LlmState } from './fixtures/llm'
import { clock } from './fixtures/time'

export function createMockDb(now = new Date(), { llmState = 'account' }: { llmState?: LlmState } = {}) {
  const c = clock(now)
  const jobs = buildJobs(c)
  const applications = buildApplications(jobs, c)
  const runs = buildRuns(c)
  return {
    clock: c,
    jobs,
    applications,
    runs,
    sources: buildSourceStatus(runs),
    agentRuns: buildAgentRuns(c),
    discarded: buildDiscarded(c),
    profileFiles: buildProfileFiles(c),
    settings: buildSettings(),
    tasks: [] as Task[],
    /** How long a mock run takes: short enough to watch, long enough to cancel. */
    runMs: 6000,
    lastRunAt: c.at(0, 7, 2),
    costMonthUsd: 4.37,
    costCapUsd: 25,
    /** Which `GET /api/llm/usage` variant to serve (fixtures/llm.ts). */
    llmState,
  }
}

export type MockDb = ReturnType<typeof createMockDb>

const LIST_KEYS = [
  'id',
  'title',
  'company',
  'location_text',
  'job_type',
  'role_category',
  'status',
  'score',
  'deadline',
  'deadline_text',
  'application_url',
  'sources',
  'first_seen',
  'is_new',
  'reposted',
  'ad_text_status',
] as const satisfies readonly (keyof JobListItem)[]

export function toListItem(job: JobDetail): JobListItem {
  return Object.fromEntries(LIST_KEYS.map((k) => [k, job[k]])) as JobListItem
}
