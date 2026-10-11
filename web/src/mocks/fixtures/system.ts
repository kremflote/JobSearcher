/** Invented source status, logs, profile files and settings. */
import type {
  AgentRunEntry,
  DerivedProfile,
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
    ['Senior backend-utvikler', 'Fjordkode AS', 'seniority_title', 'tittel inneholder «senior»'],
    ['Lead Engineer', 'Nordlys Data AS', 'seniority_title', 'tittel inneholder «lead»'],
    ['Lagermedarbeider', 'Havbris Logistikk AS', 'role', 'Ingen utviklerrolle i tittel eller tekst'],
    ['Utvikler', 'Polarstrøm Kraft AS', 'geography', 'Bergen er utenfor oslo_omegn for fast stilling'],
    ['Systemutvikler', 'Nordkapp Analytics AS', 'geography', 'Tromsø er utenfor oslo_omegn for fast stilling'],
    ['Utvikler, 5+ års erfaring', 'Stålgrid Systemer AS', 'experience_years', 'krever 5 års erfaring'],
    ['Butikksjef', 'Fjordkode AS', 'title_not_it', 'tittelen ligner ikke en IT- eller nyutdannet-stilling'],
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

type SettingDef = Pick<SettingItem, 'key' | 'section' | 'label' | 'kind' | 'default'> &
  Partial<Pick<SettingItem, 'help' | 'options' | 'min' | 'max'>> & { override?: unknown }

const GEO_MODES = ['nittedal', 'norge', 'oslo', 'oslo_omegn']
const JOB_TYPES: [string, string][] = [
  ['permanent', 'fast stilling'],
  ['trainee', 'trainee'],
  ['graduate', 'graduate'],
  ['summer', 'sommerjobb'],
]

/** Mirrors the editable keys in `web/routes/settings.py`. One override, so "Tilbakestill" shows. */
export function buildSettings(): SettingItem[] {
  const defs: SettingDef[] = [
    ...JOB_TYPES.map(
      ([t, name]): SettingDef => ({ key: `search.job_types.${t}`, section: 'search', label: `Samle inn ${name}`, kind: 'bool', default: true }),
    ),
    ...JOB_TYPES.map(
      ([t, name]): SettingDef => ({
        key: `search.geography.${t}`,
        section: 'search',
        label: `Geografi for ${name}`,
        kind: 'enum',
        options: GEO_MODES,
        default: t === 'permanent' ? 'oslo_omegn' : 'norge',
      }),
    ),
    { key: 'search.allow_remote_norway', section: 'search', label: 'Ta med fjernarbeid hos norsk arbeidsgiver', kind: 'bool', default: true },
    {
      key: 'search.role_exclude',
      section: 'search',
      label: 'Ekskluderte roller',
      kind: 'string_list',
      help: 'Tittel eller kategori med et av ordene forkastes.',
      default: ['sikkerhet', 'security', 'pentest'],
    },
    {
      key: 'search.seniority_title_exclude',
      section: 'search',
      label: 'Senioritetsord i tittel',
      kind: 'string_list',
      help: 'Gjelder kilder uten senioritetsfilter (NAV).',
      default: ['senior', 'lead', 'principal', 'arkitekt'],
    },
    {
      key: 'search.title_require_any',
      section: 'search',
      label: 'Tittelen må inneholde ett av',
      kind: 'string_list',
      help: 'Gjelder NAV før annonsen hentes. Tom liste slår regelen av.',
      default: ['utvikler', 'developer', 'it', 'data'],
    },
    {
      key: 'search.max_required_experience_years',
      section: 'search',
      label: 'Maks krav til erfaring (år)',
      kind: 'int',
      help: '0 betyr at krav på 1 år eller mer forkastes.',
      min: 0,
      max: 10,
      default: 0,
    },
    { key: 'search.unspecified_seniority_max_score', section: 'search', label: 'Maks score uten oppgitt senioritet', kind: 'int', min: 0, max: 100, default: 65 },
    { key: 'thresholds.overview_deadline_days', section: 'scoring', label: 'Frister på Oversikt (dager)', kind: 'int', min: 1, max: 60, default: 14 },
    { key: 'notify.digest', section: 'notify', label: 'Send e-postdigest', kind: 'bool', help: 'Etter den daglige kjøringen, bare når det er noe å melde.', default: true },
    {
      key: 'thresholds.notify_min_score',
      section: 'notify',
      label: 'Score for nye jobber i digesten',
      kind: 'int',
      help: 'Nye jobber med minst denne scoren kommer med.',
      min: 0,
      max: 100,
      default: 70,
      override: 75,
    },
    { key: 'notify.deadline_days', section: 'notify', label: 'Frister i digesten (dager)', kind: 'int', min: 1, max: 14, default: 3 },
    {
      key: 'llm.backend',
      section: 'llm',
      label: 'Modell-backend',
      kind: 'enum',
      options: ['openrouter', 'claude_code'],
      help: 'openrouter er DeepSeek med betalt kreditt; claude_code bruker Claude-abonnementet.',
      default: 'openrouter',
    },
    {
      key: 'llm.fallback',
      section: 'llm',
      label: 'Reserve',
      kind: 'enum',
      options: ['none', 'claude_code', 'openrouter'],
      help: 'Brukes når backenden feiler. En annen modell gir scorer på en annen skala.',
      default: 'none',
    },
    { key: 'llm.openrouter.models.fast', section: 'llm', label: 'OpenRouter-modell (fast)', kind: 'string', help: 'Brukes til scoring.', default: 'deepseek/deepseek-v4.1-flash' },
    { key: 'llm.openrouter.models.balanced', section: 'llm', label: 'OpenRouter-modell (balanced)', kind: 'string', default: 'deepseek/deepseek-v4.1-flash' },
    { key: 'llm.openrouter.models.best', section: 'llm', label: 'OpenRouter-modell (best)', kind: 'string', help: 'Brukes til søknadsbrev.', default: 'deepseek/deepseek-v4.1-flash' },
    {
      key: 'llm.monthly_cap_usd',
      section: 'cost',
      label: 'Kostnadstak per måned (USD)',
      kind: 'number',
      help: 'Gjelder betalte kall. Nås taket, stopper scoringen.',
      min: 0,
      max: 1000,
      default: 10,
    },
    { key: 'llm.warn_ratio', section: 'cost', label: 'Varsle ved andel av taket', kind: 'number', help: '0,8 = varsel ved 80 %.', min: 0.1, max: 1, default: 0.8 },
    { key: 'schedule.daily_at', section: 'schedule', label: 'Daglig kjøring', kind: 'time', help: 'Tidssone Europe/Oslo.', default: '07:00' },
    {
      key: 'schedule.jitter_minutes',
      section: 'schedule',
      label: 'Tilfeldig utsettelse (minutter)',
      kind: 'int',
      help: 'Kjøringen starter 0 til så mange minutter etter klokkeslettet.',
      min: 0,
      max: 180,
      default: 40,
    },
    { key: 'sources.finn_api.enabled', section: 'sources', label: 'Finn', kind: 'bool', default: true },
    { key: 'sources.nav.enabled', section: 'sources', label: 'NAV', kind: 'bool', help: 'Krever NAV_FEED_TOKEN i .env.', default: true },
    { key: 'sources.teamtailor.enabled', section: 'sources', label: 'Teamtailor', kind: 'bool', help: 'RSS fra karrieresidene i sources.yaml.', default: true },
    {
      key: 'sources.page_watch.enabled',
      section: 'sources',
      label: 'Karrieresider',
      kind: 'bool',
      help: 'Sjekker sidene i sources.yaml én gang i døgnet. AI leser siden bare når den har endret seg.',
      default: true,
    },
  ]
  return defs.map(({ override, ...d }) => ({
    help: null,
    options: null,
    min: null,
    max: null,
    ...d,
    value: override ?? d.default,
    overridden: override !== undefined,
  }))
}

/** Invented derived profile (layer 2), with the versions before the last regeneration. */
export function buildDerived(c: Clock): DerivedProfile {
  return {
    made_at: c.at(-3, 21),
    model: 'deepseek/deepseek-v4.1-flash',
    files: [
      {
        name: 'profile_short.md',
        content: 'Nyutdannet utvikler (bachelor 2026) med Python, TypeScript og React. Vil jobbe med backend i Oslo-området.\n',
        previous_content: 'Nyutdannet utvikler med Python og React. Vil jobbe med backend.\n',
      },
      {
        name: 'profile_long.md',
        content: '# Ola Nordmann\n\nBachelor i informatikk (2026). Deltidsutvikler hos Eksempel AS. Bookingsystem med FastAPI og React.\n',
        previous_content: null,
      },
      { name: 'voice.md', content: 'Kort, konkret, uten floskler.\n', previous_content: 'Kort og konkret.\n' },
    ],
  }
}
