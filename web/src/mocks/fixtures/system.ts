/** Invented source status, logs, profile files and settings. */
import type {
  AgentRunEntry,
  DiscardedEntry,
  ProfileFile,
  RunLogEntry,
  SettingItem,
  SourceName,
  SourceStatus,
} from '@/api/types'
import type { Clock } from './time'

const SOURCES: SourceName[] = ['finn_api', 'nav', 'teamtailor', 'page_watch']

export function buildRuns(c: Clock): RunLogEntry[] {
  const runs: RunLogEntry[] = []
  let id = 1
  for (let d = -6; d <= 0; d++) {
    for (const source of SOURCES) {
      const navBroken = source === 'nav' && d === 0
      runs.push({
        id: id++,
        trigger: d === -3 && source === 'finn_api' ? 'manual' : 'schedule',
        source,
        started_at: c.at(d, 7, 0),
        finished_at: c.at(d, 7, 2),
        found: navBroken ? 0 : 20 + ((id * 7) % 30),
        new: navBroken ? 0 : (id * 3) % 6,
        updated: (id * 5) % 4,
        filtered_out: (id * 11) % 9,
        errors: navBroken ? ['HTTP 401 fra NAV-feeden: token utløpt?'] : [],
        health: navBroken ? 'fail' : source === 'page_watch' && d === -2 ? 'warn' : 'ok',
      })
    }
  }
  return runs.reverse()
}

export function buildSourceStatus(runs: RunLogEntry[]): SourceStatus[] {
  const statuses: SourceStatus[] = SOURCES.map((source) => {
    const last = runs.find((r) => r.source === source)!
    return {
      source,
      health: last.health,
      last_run_at: last.finished_at,
      found: last.found,
      new: last.new,
      message: last.errors[0] ?? null,
    }
  })
  statuses.push({ source: 'manual', health: null, last_run_at: null, found: null, new: null, message: null })
  return statuses
}

export function buildAgentRuns(c: Clock): AgentRunEntry[] {
  const agents = ['filter', 'filter', 'filter', 'researcher', 'writer', 'reviser']
  return Array.from({ length: 24 }, (_, i): AgentRunEntry => {
    const agent = agents[i % agents.length]!
    const big = agent === 'writer' || agent === 'researcher'
    return {
      id: 24 - i,
      agent,
      backend: 'claude_code',
      model: agent === 'filter' ? 'claude-haiku-5-5' : 'claude-sonnet-5-5',
      prompt_version: '0.1',
      input_tokens: big ? 9000 + i * 100 : 4200 + i * 50,
      output_tokens: big ? 1200 : 600,
      cost_usd: big ? 0.11 : 0.02,
      duration_ms: big ? 41000 : 9000 + i * 300,
      status: i === 5 ? 'error' : 'ok',
      error: i === 5 ? 'Svaret var ikke gyldig JSON (forsøkt på nytt 2 ganger)' : null,
      created_at: c.at(-Math.floor(i / 4), 7, 5 + (i % 4) * 3),
    }
  })
}

export function buildDiscarded(c: Clock): DiscardedEntry[] {
  const rows: [string, string, string, string | null][] = [
    ['Senior backend-utvikler', 'Fjordkode AS', 'seniority', 'Tittel inneholder "senior"'],
    ['Lead Engineer', 'Nordlys Data AS', 'seniority', 'Tittel inneholder "lead"'],
    ['Lagermedarbeider', 'Havbris Logistikk AS', 'role', 'Ingen utviklerrolle i tittel eller tekst'],
    ['Utvikler', 'Polarstrøm Kraft AS', 'geography', 'Bergen er utenfor oslo_omegn for fast stilling'],
    ['Systemutvikler', 'Nordkapp Analytics AS', 'geography', 'Tromsø er utenfor oslo_omegn for fast stilling'],
    ['Utvikler, 5+ års erfaring', 'Stålgrid Systemer AS', 'experience', 'Krever minst 5 års erfaring'],
    ['Junior utvikler', 'Fjordkode AS', 'duplicate', 'Samme annonse som jobb 1001 (NAV)'],
    ['Butikkmedarbeider', 'Grønnli Handel AS', 'role', 'Ingen utviklerrolle i tittel eller tekst'],
  ]
  return rows.map(([title, company, rule, detail], i) => ({
    id: i + 1,
    job_id: 2001 + i,
    title,
    company,
    rule,
    detail,
    created_at: c.at(-Math.floor(i / 3), 7, 1),
  }))
}

export function buildProfileFiles(c: Clock): ProfileFile[] {
  const files: [string, string][] = [
    [
      'profile.yaml',
      `name: Ola Nordmann\nlocation: Bjørkely\nemail: ola@example.com\neducation:\n  - degree: Bachelor i informatikk\n    school: Eksempel høyskole\n    year: 2026\nroles: [backend, fullstack]\ntech: [Python, TypeScript, React, PostgreSQL, Docker]\n`,
    ],
    [
      'cv.md',
      `# Ola Nordmann\n\nNyutdannet utvikler (bachelor i informatikk, 2026).\n\n## Erfaring\n- Deltidsutvikler, Eksempel AS (2024–2026)\n- Bachelorprosjekt: bookingsystem for et oppdiktet idrettslag\n`,
    ],
    ['motivation.md', `# Motivasjon\n\nJeg vil jobbe med backend og lære av erfarne kolleger i et team som leverer ofte.\n`],
    ['style_overrides.md', `# Stil\n\n- Kort og konkret\n- Unngå floskler som "brennende engasjement"\n`],
    ['projects/bookingsystem.md', `# Bookingsystem\n\nFastAPI + React. Ledet backend og testoppsett.\n`],
    ['projects/vaerapp.md', `# Værapp\n\nLiten React Native-app mot et åpent vær-API.\n`],
    ['experience/eksempel-as.md', `# Eksempel AS\n\nDeltidsutvikler. Vedlikehold av interne verktøy i Python.\n`],
    ['writing_samples/soknad-1.md', `Hei,\n\nJeg søker på stillingen som …\n`],
  ]
  return files.map(([path, content], i) => ({
    path,
    content,
    content_hash: `mock${String(i).padStart(4, '0')}`,
    updated_at: c.at(-10 + i, 20),
  }))
}

export function buildSettings(): SettingItem[] {
  const items: [string, string, unknown, unknown?][] = [
    ['search', 'search.geo_mode', { permanent: 'oslo_omegn', trainee: 'norge', graduate: 'norge', summer: 'norge' }],
    ['search', 'search.job_types', ['permanent', 'trainee', 'graduate', 'summer']],
    ['search', 'search.exclude_terms', ['senior', 'lead', 'principal', 'arkitekt']],
    ['search', 'search.unspecified_seniority_max_score', 65],
    ['scoring', 'scoring.notify_threshold', 70, 75],
    ['llm', 'llm.backend', 'claude_code'],
    ['llm', 'llm.models.filter', 'claude-haiku-5-5'],
    ['llm', 'llm.models.writer', 'claude-sonnet-5-5'],
    ['cost', 'cost.monthly_cap_usd', 25],
    ['schedule', 'schedule.daily_at', '07:00'],
  ]
  return items.map(([section, key, def, override]) => ({
    key,
    section,
    default: def,
    value: override ?? def,
    overridden: override !== undefined,
  }))
}
