import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, History, Loader2, RotateCcw, Save, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useBlocker, useSearchParams } from 'react-router'
import { ApiError } from '@/api/client'
import { saveProfileFile, useProfileFile, useProfileRevisions } from '@/api/queries'
import type { ProfileFile, ProfileRevision } from '@/api/types'
import { Markdown } from '@/components/Markdown'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { diffStats, diffWords, wordCount } from '@/features/drafts/diff'
import { DiffText } from '@/features/drafts/DiffText'
import { Segmented } from '@/features/drafts/Segmented'
import { fmtVersionTime } from '@/features/drafts/Versions'
import { cn } from '@/lib/utils'
import { isYaml } from './paths'

type Mode = 'edit' | 'preview'

/**
 * One profile file (FRONTEND §5.6): Markdown editor with preview (YAML as plain monospace text),
 * explicit "Lagre" (Ctrl+S), and history with diff and "Gjenopprett". Leaving with unsaved text
 * asks first, in the app and in the browser.
 */
export function FileEditor({ path, showBack }: { path: string; showBack: boolean }) {
  const file = useProfileFile(path)
  if (file.isPending) return <Skeleton className="h-96 w-full" />
  if (file.isError || !file.data)
    return (
      <div className="text-sm">
        <p className="text-muted-foreground mb-2">
          {file.error instanceof ApiError && file.error.status === 404 ? 'Filen finnes ikke.' : 'Kunne ikke hente filen.'}
        </p>
        <Button size="sm" variant="outline" asChild>
          <Link to="/profil">Til profilen</Link>
        </Button>
      </div>
    )
  return <Editor key={path} file={file.data} showBack={showBack} />
}

function Editor({ file, showBack }: { file: ProfileFile; showBack: boolean }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [text, setText] = useState(file.content)
  const [base, setBase] = useState(file)
  const [mode, setMode] = useState<Mode>('edit')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const yaml = isYaml(file.path)
  const dirty = text !== base.content
  const showHistory = params.get('historikk') === '1'

  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty && currentLocation.pathname !== nextLocation.pathname)
  useEffect(() => {
    if (blocker.state !== 'blocked') return
    if (window.confirm('Du har endringer som ikke er lagret. Forkaste dem?')) blocker.proceed()
    else blocker.reset()
  }, [blocker])
  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  const save = async (content = text, message = 'Lagret') => {
    setSaving(true)
    setError(null)
    try {
      const saved = await saveProfileFile(qc, file.path, content, base.content_hash)
      setBase(saved)
      setText(saved.content)
      toast({ message })
      return true
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, 'unknown', 'Kunne ikke lagre.'))
      return false
    } finally {
      setSaving(false)
    }
  }

  const reload = async () => {
    const fresh = await qc.fetchQuery({ queryKey: ['profile', 'file', file.path], staleTime: 0 })
    const f = fresh as ProfileFile
    setBase(f)
    setText(f.content)
    setError(null)
  }

  const restore = async (rev: ProfileRevision) => {
    if (dirty && !window.confirm('Du har endringer som ikke er lagret. Forkaste dem og gjenopprette?')) return
    if (await save(rev.content, `Gjenopprettet versjonen fra ${fmtVersionTime(rev.created_at)}`))
      setParams({}, { replace: true })
  }

  const status = saving ? 'Lagrer …' : dirty ? 'Ikke lagret' : 'Lagret'

  return (
    <div
      className="flex flex-col gap-3"
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
          e.preventDefault()
          if (dirty && !saving) save()
        }
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        {showBack && (
          <Button size="icon-sm" variant="ghost" asChild>
            <Link to="/profil" aria-label="Tilbake til profilfilene">
              <ArrowLeft />
            </Link>
          </Button>
        )}
        <h2 className="min-w-0 truncate font-mono text-sm font-medium">{file.path}</h2>
        <span className={cn('text-xs', dirty ? 'text-warn' : 'text-muted-foreground')} data-testid="save-status">
          {status}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <Button
            size="sm"
            variant={showHistory ? 'secondary' : 'ghost'}
            aria-pressed={showHistory}
            onClick={() => setParams(showHistory ? {} : { historikk: '1' }, { replace: true })}
          >
            <History /> Historikk
          </Button>
          <Button size="sm" disabled={!dirty || saving} onClick={() => save()}>
            {saving ? <Loader2 className="animate-spin" /> : <Save />} Lagre
          </Button>
        </div>
      </div>

      {error && (
        <div role="alert" className="border-bad/40 bg-bad-soft flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm">
          <span className="min-w-0 flex-1">{error.message}</span>
          {error.code === 'conflict' && (
            <Button size="xs" variant="outline" onClick={reload}>
              Last inn på nytt (forkaster endringene dine)
            </Button>
          )}
        </div>
      )}

      {showHistory ? (
        <RevisionHistory path={file.path} current={text} onRestore={restore} onClose={() => setParams({}, { replace: true })} />
      ) : (
        <>
          {!yaml && (
            <div className="flex items-center gap-2">
              <Segmented<Mode>
                label="Visning"
                value={mode}
                onChange={setMode}
                options={[
                  { value: 'edit', label: 'Rediger' },
                  { value: 'preview', label: 'Forhåndsvis' },
                ]}
              />
              <span className="text-muted-foreground ml-auto text-xs tabular-nums">{wordCount(text)} ord</span>
            </div>
          )}
          {mode === 'edit' || yaml ? (
            <textarea
              aria-label={`Innhold i ${file.path}`}
              value={text}
              onChange={(e) => setText(e.target.value)}
              spellCheck={!yaml}
              lang="nb"
              className={cn(
                'border-input bg-background focus-visible:ring-ring field-sizing-content min-h-96 w-full resize-y rounded-md border px-3 py-2 outline-none focus-visible:ring-2',
                yaml ? 'font-mono text-[13px] leading-5' : 'text-sm leading-relaxed',
              )}
            />
          ) : (
            <div className="min-h-96 rounded-md border px-4 py-3 text-sm" data-testid="preview">
              <Markdown text={text} />
            </div>
          )}
        </>
      )}
    </div>
  )
}

/** Saved versions, newest first; selecting one shows what restoring it would change. */
function RevisionHistory({
  path,
  current,
  onRestore,
  onClose,
}: {
  path: string
  current: string
  onRestore: (rev: ProfileRevision) => void
  onClose: () => void
}) {
  const revisions = useProfileRevisions(path)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const list = revisions.data ?? []
  const selected = list.find((r) => r.id === selectedId) ?? null
  const parts = useMemo(() => (selected ? diffWords(current, selected.content) : null), [selected, current])
  const stats = parts ? diffStats(parts) : null

  return (
    <section aria-label="Historikk" className="flex flex-col gap-3" data-testid="profile-history">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">Historikk</h3>
        <Button size="icon-sm" variant="ghost" className="ml-auto" aria-label="Lukk historikken" onClick={onClose}>
          <X />
        </Button>
      </div>
      {revisions.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : !list.length ? (
        <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
          Ingen lagrede versjoner ennå. Hver lagring fra dashboardet blir en versjon.
        </p>
      ) : (
        <ul className="bg-card divide-y rounded-lg border text-sm">
          {list.map((r, i) => (
            <li key={r.id}>
              <button
                type="button"
                aria-pressed={r.id === selectedId}
                onClick={() => setSelectedId(r.id === selectedId ? null : r.id)}
                className={cn('hover:bg-muted/50 flex w-full items-center gap-2 px-3 py-2 text-left', r.id === selectedId && 'bg-muted')}
              >
                <span className="flex-1">{fmtVersionTime(r.created_at)}</span>
                <span className="text-muted-foreground text-xs">
                  {i === 0 ? 'Nyeste' : i === list.length - 1 ? 'Eldste' : ''}
                  {r.content === current ? ' · som nå' : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {selected && parts && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-muted-foreground">
              Gjenoppretting endrer teksten slik: <span className="text-good">+{stats!.added}</span>{' '}
              <span className="text-bad">−{stats!.removed}</span> ord
            </span>
            <Button size="sm" variant="outline" className="ml-auto" disabled={selected.content === current} onClick={() => onRestore(selected)}>
              <RotateCcw /> Gjenopprett
            </Button>
          </div>
          <DiffText parts={parts} />
        </div>
      )}
    </section>
  )
}
