import { Check, Copy, Download, ExternalLink, History, Loader2, Send } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { ApiError } from '@/api/client'
import { downloadDocx, draftQuery, useApplications, useDraft, useDrafts, useMessages, useRevise, useTask } from '@/api/queries'
import type { ApplicationCard, DraftSummary } from '@/api/types'
import { DeadlineBadge, StatusBadge } from '@/components/badges'
import { Page } from '@/components/Page'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import { useMove } from '@/features/tracker/useMove'
import { useIsWide } from '@/lib/useMediaQuery'
import { cn } from '@/lib/utils'
import { ClaimsBar } from './ClaimsBar'
import { DraftPane } from './DraftPane'
import { RevisionChat } from './RevisionChat'
import { Segmented } from './Segmented'
import { StartDraftButton } from './StartDraftButton'
import { useDraftEditor, type SaveState } from './useDraftEditor'
import { authorLabel, fmtVersionTime, VersionList, VersionView } from './Versions'

type View = 'utkast' | 'chat' | 'versjoner'
const VIEWS: { value: View; label: string }[] = [
  { value: 'utkast', label: 'Utkast' },
  { value: 'chat', label: 'Chat' },
  { value: 'versjoner', label: 'Versjoner' },
]

const SAVE_LABEL: Record<SaveState, string> = {
  saved: 'Lagret',
  dirty: 'Ikke lagret',
  saving: 'Lagrer …',
  error: 'Kunne ikke lagre',
}

/** Markdown → plain text for pasting into application forms. */
export const toPlainText = (md: string) =>
  md
    .replace(/^#{1,3}\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*\s][^*]*)\*/g, '$1')

/**
 * `/soknader/:applicationId` (FRONTEND §5.5). PC: text on the left, revision chat on the right,
 * version menu and actions in the toolbar. Mobile: Utkast | Chat | Versjoner (`?vis=`).
 * `?versjon=<id>` shows that version as a diff.
 */
export function EditorPage() {
  const id = Number(useParams().applicationId)
  const wide = useIsWide()
  const qc = useQueryClient()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const apps = useApplications()
  const card = apps.data?.items.find((c) => c.id === id)
  const drafts = useDrafts(id)
  const versions = drafts.data ?? []
  const latest = useDraft(versions.at(-1)?.id ?? null)
  const editor = useDraftEditor(id, latest.data)
  const base = useDraft(editor.baseId)
  const messages = useMessages(id)
  const revise = useRevise(id)
  const [pending, setPending] = useState<{ instruction: string; taskId: string | null } | null>(null)
  const task = useTask(pending?.taskId ?? null)
  const revising = !!pending && (!task.data || task.data.status === 'queued' || task.data.status === 'running')

  const selectedId = Number(params.get('versjon')) || null
  const view = (params.get('vis') as View | null) ?? 'utkast'
  const setParam = (key: string, value: string | null) =>
    setParams(
      (p) => {
        if (value === null) p.delete(key)
        else p.set(key, value)
        return p
      },
      { replace: key === 'vis' },
    )
  /** Shows a version as a diff; on mobile that happens in the Versjoner segment. */
  const selectVersion = (vid: number | null) =>
    setParams((p) => {
      if (vid === null) p.delete('versjon')
      else {
        p.set('versjon', String(vid))
        if (!wide) p.set('vis', 'versjoner')
      }
      return p
    })

  const send = async (instruction: string) => {
    setPending({ instruction, taskId: null })
    await editor.flush()
    revise.mutate(
      { instruction, draft_id: editor.baseId },
      {
        onSuccess: (r) => setPending({ instruction, taskId: r.task_id }),
        onError: (e) => {
          setPending(null)
          toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke sende instruksjonen.' })
        },
      },
    )
  }

  const restore = async (vid: number) => {
    const draft = await qc.fetchQuery(draftQuery(vid))
    await editor.restore(draft)
    selectVersion(null)
    toast({ message: `Gjenopprettet versjon ${draft.version}` })
  }

  if (drafts.isError) {
    return (
      <Page title="Søknad">
        <p className="text-muted-foreground text-sm">
          {drafts.error instanceof ApiError && drafts.error.status === 404 ? 'Fant ikke søknaden.' : 'Kunne ikke hente utkastene.'}
        </p>
      </Page>
    )
  }

  const title = card?.job_title ?? 'Søknad'
  if (drafts.data && !versions.length) {
    return (
      <Page title={title}>
        <div className="mx-auto max-w-xl rounded-lg border border-dashed p-6 text-sm">
          <p className="text-muted-foreground mb-3">Denne søknaden har ikke noe utkast ennå.</p>
          {card && <StartDraftButton jobId={card.job_id} />}
        </div>
      </Page>
    )
  }

  const chat = (
    <RevisionChat
      messages={messages.data ?? []}
      versions={versions}
      pending={pending && { instruction: pending.instruction, stored: pending.taskId !== null, task: task.data }}
      onSend={send}
      onSelectVersion={selectVersion}
      disabled={!editor.baseId}
      className={wide ? 'h-full' : undefined}
    />
  )
  const versionView = selectedId !== null && (
    <VersionView
      key={selectedId}
      versions={versions}
      selectedId={selectedId}
      currentId={editor.baseId}
      onRestore={restore}
      onClose={() => selectVersion(null)}
    />
  )
  const draftArea = (
    <div className="flex flex-col gap-3">
      <ClaimsBar applicationId={id} claims={base.data?.claims_to_verify ?? []} />
      <DraftPane text={editor.text} onChange={editor.edit} revising={revising} />
    </div>
  )

  return (
    <Page title={title} className="p-0" actions={<SaveStatus state={editor.state} />}>
      {wide ? (
        <div className="grid grid-cols-[minmax(0,1fr)_24rem]">
          <div className="flex min-w-0 flex-col gap-3 p-4">
            <Toolbar
              card={card}
              text={editor.text}
              flush={editor.flush}
              baseId={editor.baseId}
              versions={
                <VersionMenu versions={versions} currentId={editor.baseId} onSelect={selectVersion} />
              }
            />
            {versionView || draftArea}
          </div>
          <aside className="sticky top-12 h-[calc(100dvh-3rem)] border-l">{chat}</aside>
        </div>
      ) : (
        <div className="flex flex-col gap-3 p-4 pb-0">
          <Toolbar card={card} text={editor.text} flush={editor.flush} baseId={editor.baseId} />
          <Segmented<View> label="Del" value={view} onChange={(v) => setParam('vis', v)} options={VIEWS} />
          {view === 'utkast' && <div className="pb-4">{draftArea}</div>}
          {view === 'chat' && <div className="-mx-4">{chat}</div>}
          {view === 'versjoner' && (
            <div className="pb-4">
              {versionView || <VersionList versions={versions} currentId={editor.baseId} onSelect={selectVersion} />}
            </div>
          )}
        </div>
      )}
    </Page>
  )
}

function SaveStatus({ state }: { state: SaveState }) {
  return (
    <span
      className={cn('flex items-center gap-1 text-xs', state === 'error' ? 'text-bad' : 'text-muted-foreground')}
      data-testid="save-status"
      aria-live="polite"
    >
      {state === 'saving' ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : state === 'saved' && <Check className="size-3.5" aria-hidden />}
      {SAVE_LABEL[state]}
    </span>
  )
}

function VersionMenu({
  versions,
  currentId,
  onSelect,
}: {
  versions: DraftSummary[]
  currentId: number | null
  onSelect: (id: number) => void
}) {
  const current = versions.find((v) => v.id === currentId)
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="sm" variant="outline">
          <History /> {current ? `Versjon ${current.version}` : 'Versjoner'}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-h-96 w-72 overflow-y-auto">
        <DropdownMenuLabel>Vis endringer i en versjon</DropdownMenuLabel>
        {[...versions].reverse().map((v) => (
          <DropdownMenuItem key={v.id} onSelect={() => onSelect(v.id)} className="flex-col items-start gap-0">
            <span>
              Versjon {v.version}
              <span className="text-muted-foreground">
                {' '}
                · {authorLabel(v)} · {fmtVersionTime(v.created_at)}
              </span>
              {v.id === currentId && <span className="text-good"> · gjeldende</span>}
            </span>
            {(v.change_summary || v.instruction) && (
              <span className="text-muted-foreground w-full truncate text-xs">{v.change_summary ?? v.instruction}</span>
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Job facts, "Merk som søkt", copy and `.docx` download. */
function Toolbar({
  card,
  text,
  flush,
  baseId,
  versions,
}: {
  card: ApplicationCard | undefined
  text: string | null
  flush: () => Promise<void>
  baseId: number | null
  versions?: ReactNode
}) {
  const toast = useToast()
  const move = useMove()
  const [downloading, setDownloading] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(toPlainText(text ?? ''))
      toast({ message: 'Kopiert som ren tekst' })
    } catch {
      toast({ message: 'Kunne ikke kopiere.' })
    }
  }
  const download = async () => {
    setDownloading(true)
    try {
      await flush()
      if (baseId === null) return
      await downloadDocx(baseId, `Søknad ${card?.company ?? ''}.docx`)
    } catch (e) {
      toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke laste ned.' })
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="editor-toolbar">
      {card ? (
        <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground truncate">{card.company}</span>
          <StatusBadge status={card.status} />
          {(card.status === 'interessant' || card.status === 'utkast') && <DeadlineBadge deadline={card.deadline} />}
          <Link to={`/jobber/${card.job_id}`} className="text-primary inline-flex items-center gap-1 text-xs underline-offset-4 hover:underline">
            <ExternalLink className="size-3" aria-hidden /> Jobben
          </Link>
        </div>
      ) : (
        <Skeleton className="h-5 w-48" />
      )}
      <div className="ml-auto flex flex-wrap items-center gap-1">
        {versions}
        <Button size="sm" variant="outline" onClick={copy} disabled={text === null}>
          <Copy /> Kopier
        </Button>
        <Button size="sm" variant="outline" onClick={download} disabled={downloading || baseId === null}>
          {downloading ? <Loader2 className="animate-spin" /> : <Download />} .docx
        </Button>
        {card?.allowed_next.includes('sokt') && (
          <Button size="sm" onClick={() => move(card, 'sokt')}>
            <Send /> Merk som søkt
          </Button>
        )}
      </div>
    </div>
  )
}
