/** In-memory mock database built from the invented fixtures. Rebuilt on every page load. */
import type { JobDetail, JobListItem, ProfileRevision, Task } from '@/api/types'
import type { TaskSpec } from './handlers'
import { buildApplications } from './fixtures/applications'
import { buildJobs } from './fixtures/jobs'
import {
  buildAgentRuns,
  buildDerived,
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
    /** Saved versions per path, newest first (the original is kept on first save, like the API). */
    profileRevisions: new Map<string, ProfileRevision[]>(),
    profileTemplates: new Map<string, string>([
      ['projects', '---\ntech: []\nrole:\nlink:\n---\n# Prosjektnavn\n\nHva du gjorde og hva du lærte.\n'],
      ['experience', '# Arbeidsgiver\n\nRolle, periode og oppgaver.\n'],
    ]),
    profileFolders: ['experience', 'projects', 'writing_samples'],
    derived: buildDerived(c),
    derivedOutdated: true,
    /** Jobs scored with an older profile; a distill raises it, a rescore clears it. */
    staleJobs: 12,
    settings: buildSettings(),
    tasks: [] as Task[],
    taskSpecs: new Map<string, TaskSpec>(),
    /** How long mock tasks take: short enough to watch, long enough to cancel. */
    runMs: 6000,
    draftMs: 5000,
    reviseMs: 3000,
    distillMs: 4000,
    rescoreMs: 5000,
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
