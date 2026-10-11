import { ChevronRight, RotateCcw, X } from 'lucide-react'
import { useEffect, useId, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { ApiError } from '@/api/client'
import { useSettings, useUpdateSettings } from '@/api/queries'
import type { SettingItem } from '@/api/types'
import { Page } from '@/components/Page'
import { ThemeMenu } from '@/components/ThemeMenu'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { formatValue, parseNumber, SECTIONS, splitWords } from './fields'
import { RescoreCard } from './RescoreCard'

type Save = (key: string, value: unknown) => Promise<boolean>

/**
 * Innstillinger (FRONTEND §5.7): one form with sections. Each field saves on its own (toggles and
 * menus at once, text and numbers on blur or Enter) as an override of the YAML value; overridden
 * fields show the default and "Tilbakestill".
 */
export function SettingsPage() {
  const settings = useSettings()
  const update = useUpdateSettings()
  const toast = useToast()

  const save: Save = async (key, value) => {
    try {
      await update.mutateAsync({ [key]: value })
      return true
    } catch (e) {
      toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke lagre innstillingen.' })
      return false
    }
  }

  return (
    <Page title="Innstillinger">
      {settings.isPending ? (
        <div className="mx-auto flex max-w-2xl flex-col gap-3" aria-busy="true">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : settings.isError ? (
        <div className="text-sm">
          <p className="text-muted-foreground mb-2">Kunne ikke hente innstillingene.</p>
          <Button size="sm" variant="outline" onClick={() => settings.refetch()}>
            Prøv igjen
          </Button>
        </div>
      ) : (
        <div className="mx-auto flex max-w-2xl flex-col gap-8 pb-8">
          {SECTIONS.map((section) => {
            const items = settings.data.items.filter((i) => i.section === section.id)
            if (!items.length) return null
            return (
              <SettingsSection key={section.id} id={section.id} title={section.title} intro={section.intro}>
                {items.map((item) => (
                  <SettingRow key={item.key} item={item} save={save} />
                ))}
                {section.id === 'scoring' && <RescoreCard className="mt-2" />}
              </SettingsSection>
            )
          })}
          <SettingsSection id="context" title="Kontekst">
            <Link to="/profil" className="hover:bg-muted/50 -mx-1 flex items-center gap-2 rounded-md px-1 py-2 text-sm">
              Profilen agentene bruker (CV, prosjekter, motivasjon, stil)
              <ChevronRight className="text-muted-foreground ml-auto size-4" aria-hidden />
            </Link>
          </SettingsSection>
          <SettingsSection id="appearance" title="Utseende">
            <div className="flex items-center justify-between py-1 text-sm">
              Tema
              <ThemeMenu />
            </div>
          </SettingsSection>
        </div>
      )}
    </Page>
  )
}

function SettingsSection({ id, title, intro, children }: { id: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section aria-labelledby={`settings-${id}`} data-testid={`settings-${id}`}>
      <h2 id={`settings-${id}`} className="text-sm font-semibold">
        {title}
      </h2>
      {intro && <p className="text-muted-foreground mt-0.5 text-xs">{intro}</p>}
      <div className="mt-2 flex flex-col divide-y rounded-lg border px-3">{children}</div>
    </section>
  )
}

function SettingRow({ item, save }: { item: SettingItem; save: Save }) {
  const id = useId()
  const inline = item.kind === 'bool'
  // Word lists take the full width, so their label always sits above them.
  const stacked = item.kind === 'string_list'
  return (
    <div className="py-3" data-testid={`setting-${item.key}`}>
      <div
        className={cn(
          'flex gap-3',
          inline ? 'items-center' : stacked ? 'flex-col gap-1.5' : 'flex-col gap-1.5 sm:flex-row sm:items-center',
        )}
      >
        <label htmlFor={id} className="min-w-0 flex-1 text-sm">
          {item.label}
          {item.help && <span className="text-muted-foreground block text-xs">{item.help}</span>}
        </label>
        <div className={cn(stacked ? 'w-full' : !inline && 'sm:w-56')}>
          <SettingInput id={id} item={item} save={save} />
        </div>
      </div>
      {item.overridden && (
        <div className="text-muted-foreground mt-1.5 flex items-center gap-2 text-xs">
          <span className="min-w-0 truncate">Standard: {formatValue(item, item.default)}</span>
          <Button size="xs" variant="ghost" onClick={() => save(item.key, null)} aria-label={`Tilbakestill ${item.label}`}>
            <RotateCcw /> Tilbakestill
          </Button>
        </div>
      )}
    </div>
  )
}

const INPUT =
  'border-input bg-background focus-visible:ring-ring h-9 w-full rounded-md border px-3 text-sm outline-none focus-visible:ring-2'

function SettingInput({ id, item, save }: { id: string; item: SettingItem; save: Save }) {
  switch (item.kind) {
    case 'bool':
      return <Toggle id={id} checked={item.value === true} onChange={(v) => save(item.key, v)} />
    case 'enum':
      return (
        <select id={id} className={INPUT} value={String(item.value)} onChange={(e) => save(item.key, e.target.value)}>
          {(item.options ?? []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      )
    case 'string_list':
      return <WordList id={id} item={item} save={save} />
    default:
      return <TextInput id={id} item={item} save={save} />
  }
}

function Toggle({ id, checked, onChange }: { id: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        'focus-visible:ring-ring relative inline-flex h-6 w-10 shrink-0 items-center rounded-full transition-colors outline-none focus-visible:ring-2',
        checked ? 'bg-primary' : 'bg-input',
      )}
    >
      <span
        className={cn('bg-background size-5 rounded-full shadow transition-transform', checked ? 'translate-x-4.5' : 'translate-x-0.5')}
      />
    </button>
  )
}

/** Text, number and time fields: edited locally, saved on blur or Enter; Escape reverts. */
function TextInput({ id, item, save }: { id: string; item: SettingItem; save: Save }) {
  const shown = item.kind === 'int' || item.kind === 'number' ? formatValue(item, item.value) : String(item.value ?? '')
  const [text, setText] = useState(shown)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => setText(shown), [shown])

  const commit = async () => {
    if (text === shown) return setError(null)
    let value: unknown = text.trim()
    if (item.kind === 'int' || item.kind === 'number') {
      value = parseNumber(text, item.kind)
      if (value === null) return setError(item.kind === 'int' ? 'Skriv et heltall.' : 'Skriv et tall.')
    }
    setError(null)
    if (!(await save(item.key, value))) setText(shown)
  }

  return (
    <>
      <input
        id={id}
        className={cn(INPUT, error && 'border-bad')}
        type={item.kind === 'time' ? 'time' : 'text'}
        inputMode={item.kind === 'int' ? 'numeric' : item.kind === 'number' ? 'decimal' : undefined}
        value={text}
        aria-invalid={!!error}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.currentTarget.blur()
          if (e.key === 'Escape') {
            setText(shown)
            setError(null)
          }
        }}
      />
      {error && <p className="text-bad mt-1 text-xs">{error}</p>}
    </>
  )
}

/** Word list as removable chips plus a field that adds on Enter or comma. */
function WordList({ id, item, save }: { id: string; item: SettingItem; save: Save }) {
  const words = Array.isArray(item.value) ? (item.value as string[]) : []
  const [text, setText] = useState('')

  const add = async () => {
    const extra = splitWords(text).filter((w) => !words.includes(w))
    if (!extra.length) return setText('')
    if (await save(item.key, [...words, ...extra])) setText('')
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {words.map((w) => (
        <span key={w} className="bg-muted inline-flex h-6 items-center gap-0.5 rounded-md pr-0.5 pl-2 text-xs">
          {w}
          <button
            type="button"
            aria-label={`Fjern ${w}`}
            className="hover:bg-background/60 rounded p-0.5"
            onClick={() => save(item.key, words.filter((x) => x !== w))}
          >
            <X className="size-3" />
          </button>
        </span>
      ))}
      <input
        id={id}
        className="border-input bg-background focus-visible:ring-ring h-7 min-w-32 flex-1 rounded-md border px-2 text-sm outline-none focus-visible:ring-2"
        placeholder="Legg til …"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => text.trim() && add()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault()
            add()
          }
        }}
      />
    </div>
  )
}
