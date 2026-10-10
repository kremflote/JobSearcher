/**
 * Invented jobs. Every company, person and ad text here is made up (AGENTS.md: never real data).
 */
import type { ApplicationStatus, Contact, JobDetail, JobType, SourceName } from '@/api/types'
import type { Clock } from './time'

type Role = NonNullable<JobDetail['role_category']>

type Seed = {
  title: string
  company: string
  location: string
  type: JobType
  role: Role
  score: number
  /** Deadline in days from today; null = unknown (see `deadlineText`). */
  deadline: number | null
  deadlineText?: string
  status: ApplicationStatus
  sources: SourceName[]
  /** Days since first seen. 0 = found by today's run. */
  seen: number
  repost?: boolean
  titleOnly?: boolean
  remote?: JobDetail['remote']
}

// prettier-ignore
const SEEDS: Seed[] = [
  { title: 'Junior backend-utvikler', company: 'Fjordkode AS', location: 'Oslo', type: 'permanent', role: 'backend', score: 86, deadline: 3, status: 'ny', sources: ['finn_api'], seen: 0, remote: 'hybrid' },
  { title: 'Utvikler, nyutdannet', company: 'Nordlys Data AS', location: 'Oslo', type: 'permanent', role: 'fullstack', score: 82, deadline: 9, status: 'interessant', sources: ['finn_api', 'nav'], seen: 4 },
  { title: 'IT-traineeprogram 2027', company: 'Granitt Bank ASA', location: 'Oslo', type: 'trainee', role: 'other', score: 79, deadline: 12, status: 'interessant', sources: ['teamtailor'], seen: 6 },
  { title: 'Graduate Software Engineer', company: 'Isbre Energi AS', location: 'Lysaker', type: 'graduate', role: 'backend', score: 77, deadline: 20, status: 'utkast', sources: ['page_watch'], seen: 8 },
  { title: 'Frontend-utvikler (junior)', company: 'Lysverket Digital AS', location: 'Oslo', type: 'permanent', role: 'frontend', score: 74, deadline: 2, status: 'utkast', sources: ['finn_api'], seen: 10, remote: 'hybrid' },
  { title: 'Fullstack-utvikler', company: 'Tindra Konsult AS', location: 'Lillestrøm', type: 'permanent', role: 'fullstack', score: 72, deadline: null, deadlineText: 'fortløpende', status: 'ny', sources: ['finn_api'], seen: 0 },
  { title: 'Sommerjobb utvikling 2027', company: 'Havbris Logistikk AS', location: 'Oslo', type: 'summer', role: 'fullstack', score: 70, deadline: 30, status: 'ny', sources: ['teamtailor'], seen: 0 },
  { title: 'Trainee teknologi og data', company: 'Mosvik Forsikring ASA', location: 'Oslo', type: 'trainee', role: 'data', score: 68, deadline: 25, status: 'ny', sources: ['page_watch'], seen: 1 },
  { title: 'Systemutvikler', company: 'Romerike IKT', location: 'Lillestrøm', type: 'permanent', role: 'backend', score: 66, deadline: 14, status: 'ny', sources: ['nav'], seen: 2 },
  { title: 'Dataingeniør, nyutdannet', company: 'Kvartsbrudd Analyse AS', location: 'Oslo', type: 'permanent', role: 'data', score: 64, deadline: 6, status: 'ny', sources: ['finn_api'], seen: 0 },
  { title: 'Mobilutvikler (React Native)', company: 'Appvik AS', location: 'Oslo', type: 'permanent', role: 'mobile', score: 63, deadline: 16, status: 'ny', sources: ['finn_api'], seen: 0, repost: true },
  { title: 'DevOps-ingeniør, junior', company: 'Skyfjell Drift AS', location: 'Fornebu', type: 'permanent', role: 'devops', score: 61, deadline: 11, status: 'ny', sources: ['finn_api', 'nav'], seen: 3 },
  { title: 'Backend-utvikler Java', company: 'Stålgrid Systemer AS', location: 'Oslo', type: 'permanent', role: 'backend', score: 58, deadline: null, deadlineText: 'snarest', status: 'ny', sources: ['nav'], seen: 5 },
  { title: 'Graduate-program teknologi', company: 'Polarstrøm Kraft AS', location: 'Bergen', type: 'graduate', role: 'other', score: 57, deadline: 40, status: 'ny', sources: ['teamtailor'], seen: 0 },
  { title: 'Sommerstudent IT 2027', company: 'Vardvind AS', location: 'Trondheim', type: 'summer', role: 'other', score: 55, deadline: 35, status: 'ny', sources: ['page_watch'], seen: 2 },
  { title: 'Utvikler .NET', company: 'Sentrum Regnskap AS', location: 'Oslo', type: 'permanent', role: 'backend', score: 52, deadline: 8, status: 'ny', sources: ['finn_api'], seen: 1 },
  { title: 'Konsulent, utvikling', company: 'Brygge & Bit AS', location: 'Oslo', type: 'permanent', role: 'fullstack', score: 49, deadline: 13, status: 'ny', sources: ['finn_api'], seen: 0, titleOnly: true },
  { title: 'Testutvikler', company: 'Kvalitetsløkka AS', location: 'Asker', type: 'permanent', role: 'other', score: 46, deadline: 5, status: 'ny', sources: ['nav'], seen: 4 },
  { title: 'IT-konsulent med utviklerambisjoner', company: 'Lindeberg Skoler', location: 'Oslo', type: 'permanent', role: 'other', score: 41, deadline: 10, status: 'ny', sources: ['nav'], seen: 6 },
  { title: 'Embedded-utvikler', company: 'Signalmast AS', location: 'Skedsmokorset', type: 'permanent', role: 'other', score: 38, deadline: 18, status: 'ny', sources: ['finn_api'], seen: 3 },
  { title: 'Junior dataanalytiker', company: 'Måkeskjær Media AS', location: 'Oslo', type: 'permanent', role: 'data', score: 59, deadline: 4, status: 'ny', sources: ['finn_api'], seen: 1, titleOnly: true },
  { title: 'Trainee digitalisering', company: 'Fjordporten Havn KF', location: 'Oslo', type: 'trainee', role: 'other', score: 62, deadline: 1, status: 'ny', sources: ['page_watch'], seen: 9 },
  { title: 'Python-utvikler', company: 'Nittelva Tech AS', location: 'Nittedal', type: 'permanent', role: 'backend', score: 84, deadline: 7, status: 'ny', sources: ['finn_api'], seen: 0 },
  { title: 'Webutvikler', company: 'Grønnli Handel AS', location: 'Jessheim', type: 'permanent', role: 'frontend', score: 60, deadline: 15, status: 'ny', sources: ['finn_api'], seen: 0, repost: true },
  { title: 'Graduate Data & AI', company: 'Nordkapp Analytics AS', location: 'Oslo', type: 'graduate', role: 'data', score: 73, deadline: 28, status: 'ny', sources: ['teamtailor'], seen: 0 },
  { title: 'Applikasjonsutvikler', company: 'Ringvei Transport AS', location: 'Oslo', type: 'permanent', role: 'fullstack', score: 67, deadline: 21, status: 'ny', sources: ['nav'], seen: 2 },
  { title: 'Utvikler i plattformteam', company: 'Tundra Betaling AS', location: 'Oslo', type: 'permanent', role: 'devops', score: 54, deadline: 9, status: 'ny', sources: ['finn_api'], seen: 5, remote: 'full' },
  { title: 'Backend-utvikler, nyutdannet', company: 'Sølvberg Software AS', location: 'Oslo', type: 'permanent', role: 'backend', score: 81, deadline: -5, status: 'sokt', sources: ['finn_api'], seen: 24 },
  { title: 'Trainee IT og digitalisering', company: 'Høyfjell Gruppen ASA', location: 'Oslo', type: 'trainee', role: 'other', score: 76, deadline: -12, status: 'intervju', sources: ['teamtailor'], seen: 30 },
  { title: 'Junior systemutvikler', company: 'Elvebakken Data AS', location: 'Oslo', type: 'permanent', role: 'fullstack', score: 78, deadline: -20, status: 'tilbud', sources: ['finn_api'], seen: 41 },
  { title: 'Graduate Developer', company: 'Kystlinje Shipping AS', location: 'Lysaker', type: 'graduate', role: 'backend', score: 71, deadline: -9, status: 'sokt', sources: ['page_watch'], seen: 27 },
  { title: 'Utvikler, kundeplattform', company: 'Sjøstjerne Telekom AS', location: 'Fornebu', type: 'permanent', role: 'fullstack', score: 69, deadline: -30, status: 'avslag', sources: ['finn_api'], seen: 50 },
  { title: 'Juniorutvikler', company: 'Fossekall Software AS', location: 'Oslo', type: 'permanent', role: 'backend', score: 65, deadline: -25, status: 'avslag', sources: ['nav'], seen: 45 },
  { title: 'IT-trainee', company: 'Birkebeiner Sparebank', location: 'Hamar', type: 'trainee', role: 'other', score: 60, deadline: -15, status: 'trukket', sources: ['teamtailor'], seen: 38 },
  { title: 'Frontend-utvikler', company: 'Pikselbrygga AS', location: 'Oslo', type: 'permanent', role: 'frontend', score: 63, deadline: -3, status: 'utlopt', sources: ['finn_api'], seen: 19 },
  { title: 'Utvikler med lederansvar', company: 'Tårnhuset AS', location: 'Oslo', type: 'permanent', role: 'backend', score: 44, deadline: 10, status: 'ikke_aktuell', sources: ['finn_api'], seen: 3 },
  { title: 'Salgsingeniør IT', company: 'Kobberdalen AS', location: 'Drammen', type: 'permanent', role: 'other', score: 35, deadline: 14, status: 'ikke_aktuell', sources: ['nav'], seen: 4 },
  { title: 'ERP-konsulent', company: 'Mjøsa Consulting AS', location: 'Oslo', type: 'permanent', role: 'other', score: 39, deadline: 6, status: 'ikke_aktuell', sources: ['finn_api'], seen: 2 },
  { title: 'Sommerjobb backend', company: 'Bølgetopp Media AS', location: 'Oslo', type: 'summer', role: 'backend', score: 75, deadline: 4, status: 'sokt', sources: ['finn_api'], seen: 12 },
  { title: 'Trainee utvikling', company: 'Lauvhøgda Energi AS', location: 'Oslo', type: 'trainee', role: 'fullstack', score: 80, deadline: 5, status: 'interessant', sources: ['teamtailor'], seen: 7 },
  { title: 'Junior utvikler', company: 'Fjelltopp Data AS', location: 'Oslo', type: 'permanent', role: 'fullstack', score: 71, deadline: 3, status: 'interessant', sources: ['finn_api'], seen: 5 },
]

const TECH: Record<Role, string[]> = {
  backend: ['Python', 'FastAPI', 'PostgreSQL', 'Docker'],
  frontend: ['TypeScript', 'React', 'CSS', 'Vite'],
  fullstack: ['TypeScript', 'React', 'Node.js', 'PostgreSQL'],
  mobile: ['React Native', 'TypeScript', 'iOS', 'Android'],
  devops: ['Kubernetes', 'Terraform', 'Azure', 'GitHub Actions'],
  data: ['Python', 'SQL', 'dbt', 'Power BI'],
  other: ['Java', 'SQL', 'Git'],
}

const FIRST = ['Kari', 'Ola', 'Ingrid', 'Per', 'Silje', 'Jonas', 'Marte', 'Henrik', 'Nora', 'Emil']
const LAST = ['Nordmann', 'Hansen', 'Berg', 'Dahl', 'Lie', 'Moen', 'Strand', 'Haug', 'Lund', 'Vik']

function slug(s: string) {
  return s
    .toLowerCase()
    .replace(/æ/g, 'ae')
    .replace(/ø/g, 'o')
    .replace(/å/g, 'a')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
}

function contactsFor(i: number, company: string): Contact[] {
  if (i % 4 === 3) return []
  const name = `${FIRST[i % FIRST.length]} ${LAST[(i * 3) % LAST.length]}`
  const domain = `${slug(company).replace(/-(as|asa|kf)$/, '')}.example`
  const contact: Contact = {
    name,
    role: i % 2 ? 'Teamleder' : 'Rekrutteringsansvarlig',
    email: `${slug(name.split(' ')[0]!)}@${domain}`,
    phone: i % 3 ? `+47 400 00 ${String(i).padStart(3, '0')}` : null,
    source: i % 5 === 0 ? 'llm' : 'feed',
  }
  return [contact]
}

function description(s: Seed) {
  return [
    `${s.company} søker en ${s.title.toLowerCase()} til teamet vårt i ${s.location}.`,
    `Du blir en del av et lite, tverrfaglig team som utvikler og drifter interne og kundevendte løsninger. Vi jobber smidig, har kodegjennomgang på alt og deployer flere ganger i uken.`,
    `Arbeidsoppgaver:\n- Utvikle nye funksjoner sammen med erfarne kolleger\n- Skrive tester og vedlikeholde eksisterende kode\n- Delta i planlegging og designdiskusjoner`,
    `Vi ser etter deg som:\n- Har en relevant bachelor- eller mastergrad, gjerne nylig fullført\n- Har erfaring med ${TECH[s.role].slice(0, 2).join(' og ')} fra studier, prosjekter eller deltidsjobb\n- Er nysgjerrig og liker å lære\n- Snakker og skriver norsk eller engelsk flytende`,
    `Vi tilbyr fast stilling, fleksibel arbeidstid, gode pensjons- og forsikringsordninger og et faglig miljø med fokus på læring.`,
  ].join('\n\n')
}

export function buildJobs(c: Clock): JobDetail[] {
  return SEEDS.map((s, i): JobDetail => {
    const id = 1001 + i
    const tech = TECH[s.role]
    const sourceRefs = s.sources.map((source, k) => ({
      source,
      source_id: source === 'finn_api' ? String(420000000 + id * 7) : source === 'nav' ? `nav-${id}` : null,
      url:
        source === 'finn_api'
          ? `https://www.finn.no/job/ad/${420000000 + id * 7}`
          : `https://karriere.${slug(s.company)}.example/stillinger/${id}`,
      fetched_at: c.at(-s.seen + k, 7, 2),
    }))
    const confidence = s.titleOnly ? ('low' as const) : ('high' as const)
    return {
      id,
      title: s.title,
      company: s.company,
      location_text: s.location,
      job_type: s.type,
      role_category: s.role,
      status: s.status,
      score: s.score,
      deadline: s.deadline === null ? null : c.day(s.deadline),
      deadline_text: s.deadlineText ?? null,
      application_url: `https://karriere.${slug(s.company)}.example/sok/${id}`,
      sources: s.sources,
      first_seen: c.at(-s.seen, 7, 3),
      is_new: s.seen === 0,
      reposted: s.repost ?? false,
      ad_text_status: s.titleOnly ? 'missing' : 'present',
      municipality: s.location,
      remote: s.remote ?? 'none',
      seniority: 'entry',
      ad_language: i % 6 === 2 ? 'en' : 'no',
      description: s.titleOnly ? null : description(s),
      published_at: c.at(-s.seen - 1, 12),
      expires_at: s.deadline === null ? null : c.at(s.deadline, 23, 59),
      last_seen: c.at(0, 7, 3),
      reposted_from_id: s.repost ? 900 + i : null,
      evaluation: {
        score: s.score,
        confidence,
        role_category: s.role,
        seniority: 'entry',
        tech,
        summary: s.titleOnly
          ? `Bare tittelen er kjent. Ut fra tittelen ser det ut som en ${s.title.toLowerCase()}-stilling hos ${s.company}.`
          : `${s.company} ser etter en nyutdannet ${s.title.toLowerCase()} i ${s.location}. Teamet jobber smidig med ${tech.slice(0, 3).join(', ')}. Stillingen passer for noen som vil lære mye det første året.`,
        key_requirements: s.titleOnly
          ? []
          : ['Relevant utdanning', `Erfaring med ${tech[0]}`, 'Norsk eller engelsk flytende', 'Lærevillig'],
        match_reasons:
          s.score >= 60
            ? [`Du har brukt ${tech[0]} i flere prosjekter`, 'Stillingen er rettet mot nyutdannede', `Kort reisevei til ${s.location}`]
            : [`Noe overlapp med ${tech[0]}`],
        concerns:
          s.score >= 75
            ? []
            : s.score >= 50
              ? [`Lite erfaring med ${tech[2] ?? tech[1]}`]
              : ['Rollen ligger utenfor ønsket retning', `Krever erfaring med ${tech[1]}`],
        model: 'claude-haiku-5-5',
        prompt_version: '0.1',
        created_at: c.at(-s.seen, 7, 10),
      },
      contacts: contactsFor(i, s.company),
      source_refs: sourceRefs,
      company_note:
        i % 3 === 0
          ? {
              name: s.company,
              content: `**Hva de gjør:** ${s.company} er et oppdiktet selskap brukt i mock-data.\n\n**Størrelse:** ca. ${40 + i * 7} ansatte, hovedkontor i ${s.location}.\n\n**Teknologi:** ${tech.join(', ')}.`,
              quality: i % 2 ? 'limited' : 'full',
              researched_at: c.at(-s.seen, 8),
            }
          : null,
      application: null,
    }
  })
}
