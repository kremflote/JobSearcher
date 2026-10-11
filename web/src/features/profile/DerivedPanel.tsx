import { AlertTriangle, CheckCircle2, Loader2, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { ApiError } from '@/api/client'
import { isTaskActive, useDerivedProfile, useStartDistill, useTask } from '@/api/queries'
import type { DerivedFile, ProfileFileInfo } from '@/api/types'
import { Markdown } from '@/components/Markdown'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { diffStats, diffWords } from '@/features/drafts/diff'
import { DiffText } from '@/features/drafts/DiffText'
import { Segmented } from '@/features/drafts/Segmented'
import { fmtVersionTime } from '@/features/drafts/Versions'
import { RescoreCard } from '@/features/settings/RescoreCard'
import { cn } from '@/lib/utils'

/**
 * Status line (FRONTEND §5.6): "Destillert profil er utdatert" with "Regenerer" when the profile
 * hash changed, otherwise when it was made. After a regeneration, the rescore card offers to
 * score old jobs again.
 */
export function DerivedStatus({ outdated, madeAt }: { outdated: boolean; madeAt: string | null }) {
  const toast = useToast()
  const start = useStartDistill()
  const [taskId, setTaskId] = useState<string | null>(null)
  const task = useTask(taskId)
  const busy = start.isPending || (taskId !== null && (!task.data || isTaskActive(task.data)))

  const regenerate = () =>
    start.mutate(undefined, {
      onSuccess: (r) => setTaskId(r.task_id),
      onError: (e) => toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke starte destilleringen.' }),
    })

  return (
    <div className="flex flex-col gap-2">
      <div
        className={cn(
          'flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border px-3 py-2 text-sm',
          outdated && !busy && 'border-warn/50 bg-warn-soft',
        )}
        data-testid="derived-status"
      >
        {busy ? (
          <Loader2 className="text-muted-foreground size-4 animate-spin" aria-hidden />
        ) : outdated ? (
          <AlertTriangle className="text-warn size-4" aria-hidden />
        ) : (
          <CheckCircle2 className="text-good size-4" aria-hidden />
        )}
        <p className="min-w-0 flex-1">
          {busy
            ? 'Destillerer profilen …'
            : outdated
              ? 'Destillert profil er utdatert. Agentene bruker den gamle til du regenererer.'
              : `Destillert profil er oppdatert${madeAt ? ` (laget ${fmtVersionTime(madeAt)})` : ''}.`}
        </p>
        <Link to="/profil?vis=destillert" className="text-muted-foreground text-xs underline-offset-4 hover:underline">
          Vis destillert
        </Link>
        {(outdated || busy) && (
          <Button size="sm" variant={outdated ? 'default' : 'secondary'} disabled={busy} onClick={regenerate}>
            <RefreshCw className={cn(busy && 'animate-spin')} /> Regenerer
          </Button>
        )}
      </div>
      {!outdated && !busy && <RescoreCard hideWhenNone />}
    </div>
  )
}

/** The derived files (layer 2), each with what the last regeneration changed. */
export function DerivedView({ files }: { files: ProfileFileInfo[] }) {
  const derived = useDerivedProfile()
  if (derived.isPending) return <Skeleton className="h-64 w-full" />
  if (derived.isError) return <p className="text-muted-foreground text-sm">Kunne ikke hente den destillerte profilen.</p>
  if (!derived.data.files.length)
    return (
      <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
        Profilen er ikke destillert ennå.{files.length ? ' Trykk «Regenerer».' : ' Fyll ut profilfilene først.'}
      </p>
    )
  return (
    <section className="flex flex-col gap-4" aria-label="Destillert profil" data-testid="derived-view">
      <p className="text-muted-foreground text-xs">
        Laget av agentene fra profilfilene{derived.data.model ? ` med ${derived.data.model}` : ''}
        {derived.data.made_at ? `, ${fmtVersionTime(derived.data.made_at)}` : ''}. Filtrering bruker kortversjonen;
        søknadsbrev bruker den lange og stemmen. Rett opp i kildefilene, ikke her.
      </p>
      {derived.data.files.map((f) => (
        <DerivedFileCard key={f.name} file={f} />
      ))}
    </section>
  )
}

type Mode = 'text' | 'changes'

function DerivedFileCard({ file }: { file: DerivedFile }) {
  const [mode, setMode] = useState<Mode>('text')
  const parts = useMemo(
    () => (file.previous_content !== null ? diffWords(file.previous_content, file.content) : null),
    [file.previous_content, file.content],
  )
  const stats = parts ? diffStats(parts) : null
  return (
    <article className="flex flex-col gap-2" aria-label={file.name}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-mono text-sm font-medium">{file.name}</h3>
        {stats && (
          <span className="text-muted-foreground text-xs">
            Siste regenerering: <span className="text-good">+{stats.added}</span> <span className="text-bad">−{stats.removed}</span> ord
          </span>
        )}
        {parts && (
          <Segmented<Mode>
            label={`Visning av ${file.name}`}
            value={mode}
            onChange={setMode}
            options={[
              { value: 'text', label: 'Tekst' },
              { value: 'changes', label: 'Endringer' },
            ]}
            className="ml-auto"
          />
        )}
      </div>
      {mode === 'changes' && parts ? (
        <DiffText parts={parts} />
      ) : (
        <div className="rounded-lg border px-3 py-2 text-sm">
          <Markdown text={file.content} />
        </div>
      )}
    </article>
  )
}
