import type { ApplicationStatus, JobType } from '@/api/types'

/** Display names for API status values (FRONTEND §7: values are snake_case, names live here). */
export const STATUS_LABEL: Record<ApplicationStatus, string> = {
  ny: 'Ikke vurdert',
  interessant: 'Interessant',
  utkast: 'Utkast',
  sokt: 'Søkt',
  intervju: 'Intervju',
  tilbud: 'Tilbud',
  ikke_aktuell: 'Ikke aktuell',
  avslag: 'Avslag',
  trukket: 'Trukket',
  utlopt: 'Utløpt',
}

/** One fixed colour pair per status, used the same everywhere (FRONTEND §6). */
export const STATUS_CLASS: Record<ApplicationStatus, string> = {
  ny: 'bg-info-soft text-info',
  interessant: 'bg-good-soft text-good',
  utkast: 'bg-warn-soft text-warn',
  sokt: 'bg-violet-soft text-violet',
  intervju: 'bg-violet-soft text-violet',
  tilbud: 'bg-good-soft text-good',
  ikke_aktuell: 'bg-muted text-muted-foreground',
  avslag: 'bg-bad-soft text-bad',
  trukket: 'bg-muted text-muted-foreground',
  utlopt: 'bg-muted text-muted-foreground',
}

/** Statuses grouped under "Avsluttet" in the tracker (FRONTEND §5.4). */
export const CLOSED_STATUSES: readonly ApplicationStatus[] = ['ikke_aktuell', 'avslag', 'trukket', 'utlopt']

export const JOB_TYPE_LABEL: Record<JobType, string> = {
  permanent: 'Fast',
  trainee: 'Trainee',
  graduate: 'Graduate',
  summer: 'Sommerjobb',
  unknown: 'Ukjent',
}

export type TrackerColumn = { id: string; label: string; statuses: readonly ApplicationStatus[] }

/** Tracker columns on PC and groups on mobile (FRONTEND §5.4). `ny` never has an application. */
export const TRACKER_COLUMNS: readonly TrackerColumn[] = [
  { id: 'interessant', label: 'Interessant', statuses: ['interessant'] },
  { id: 'utkast', label: 'Utkast', statuses: ['utkast'] },
  { id: 'sokt', label: 'Søkt', statuses: ['sokt'] },
  { id: 'intervju', label: 'Intervju', statuses: ['intervju'] },
  { id: 'tilbud', label: 'Tilbud', statuses: ['tilbud'] },
  { id: 'avsluttet', label: 'Avsluttet', statuses: CLOSED_STATUSES },
]

export const columnOf = (status: ApplicationStatus) =>
  TRACKER_COLUMNS.find((c) => c.statuses.includes(status)) ?? TRACKER_COLUMNS[0]!
