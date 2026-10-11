import { useQueryClient } from '@tanstack/react-query'
import { FileText, Folder, Plus, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError } from '@/api/client'
import { fetchTemplate, saveProfileFile } from '@/api/queries'
import type { ProfileFileInfo } from '@/api/types'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { fileUrl, slugify } from './paths'

/** What each standard file and folder is for (ARCHITECTURE §6.1). */
const HINTS: Record<string, string> = {
  'profile.yaml': 'Fakta: kontakt, utdanning, ferdigheter',
  'cv.md': 'Full CV',
  'motivation.md': 'Hva du vil og hvorfor',
  'style_overrides.md': 'Stilregler for brev',
  projects: 'Ett prosjekt per fil',
  experience: 'Én jobb per fil',
  writing_samples: 'Egne tekster',
}

/**
 * The profile files (FRONTEND §5.6): files in the root first, then one group per folder with
 * "Ny fil", which creates a file from the folder's `_template.md`.
 */
export function FileTree({
  files,
  folders,
  selected,
  derivedSelected,
}: {
  files: ProfileFileInfo[]
  folders: string[]
  selected: string | null
  derivedSelected: boolean
}) {
  const root = files.filter((f) => !f.path.includes('/'))
  const groups = [...new Set([...folders, ...files.filter((f) => f.path.includes('/')).map((f) => f.path.split('/')[0]!)])].sort()

  return (
    <nav aria-label="Profilfiler" className="flex flex-col gap-3 text-sm">
      <ul className="flex flex-col">
        {root.map((f) => (
          <FileLink key={f.path} file={f} active={f.path === selected} />
        ))}
      </ul>
      {groups.map((folder) => (
        <FolderGroup
          key={folder}
          folder={folder}
          files={files.filter((f) => f.path.startsWith(`${folder}/`))}
          selected={selected}
        />
      ))}
      <Link
        to="/profil?vis=destillert"
        className={cn(
          'hover:bg-muted/60 flex h-9 items-center gap-2 rounded-md px-2',
          derivedSelected && 'bg-muted font-medium',
        )}
        aria-current={derivedSelected ? 'page' : undefined}
      >
        <Sparkles className="text-muted-foreground size-4" aria-hidden />
        Destillert profil
      </Link>
    </nav>
  )
}

function FileLink({ file, active, nested = false }: { file: ProfileFileInfo; active: boolean; nested?: boolean }) {
  const name = nested ? file.path.split('/').slice(1).join('/') : file.path
  const hint = HINTS[file.path]
  return (
    <li>
      <Link
        to={fileUrl(file.path)}
        aria-current={active ? 'page' : undefined}
        className={cn('hover:bg-muted/60 flex min-h-9 items-center gap-2 rounded-md px-2 py-1', active && 'bg-muted font-medium')}
      >
        <FileText className="text-muted-foreground size-4 shrink-0" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate">{name}</span>
          {hint && <span className="text-muted-foreground block truncate text-xs font-normal">{hint}</span>}
        </span>
      </Link>
    </li>
  )
}

function FolderGroup({ folder, files, selected }: { folder: string; files: ProfileFileInfo[]; selected: string | null }) {
  const [adding, setAdding] = useState(false)
  return (
    <div>
      <div className="text-muted-foreground flex h-8 items-center gap-2 px-2 text-xs font-medium">
        <Folder className="size-3.5" aria-hidden />
        <span className="flex-1 truncate" title={HINTS[folder]}>
          {folder}/
        </span>
        <Button size="icon-xs" variant="ghost" aria-label={`Ny fil i ${folder}`} onClick={() => setAdding((a) => !a)}>
          <Plus />
        </Button>
      </div>
      {adding && <NewFile folder={folder} existing={files.map((f) => f.path)} onDone={() => setAdding(false)} />}
      <ul className="flex flex-col">
        {files.map((f) => (
          <FileLink key={f.path} file={f} active={f.path === selected} nested />
        ))}
        {!files.length && !adding && <li className="text-muted-foreground px-2 py-1 text-xs">Ingen filer ennå.</li>}
      </ul>
    </div>
  )
}

function NewFile({ folder, existing, onDone }: { folder: string; existing: string[]; onDone: () => void }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const toast = useToast()
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const slug = slugify(name)
  const path = `${folder}/${slug}.md`
  const taken = existing.includes(path)

  const create = async () => {
    if (!slug || taken) return
    setBusy(true)
    try {
      const template = await fetchTemplate(folder)
      await saveProfileFile(qc, path, template, null)
      onDone()
      navigate(fileUrl(path))
    } catch (e) {
      toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke lage filen.' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      className="mb-1 flex flex-col gap-1 px-2"
      onSubmit={(e) => {
        e.preventDefault()
        create()
      }}
    >
      <div className="flex gap-1">
        <input
          autoFocus
          aria-label={`Navn på ny fil i ${folder}`}
          placeholder="Navn, f.eks. Bookingsystem"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Escape' && onDone()}
          className="border-input bg-background focus-visible:ring-ring h-8 min-w-0 flex-1 rounded-md border px-2 text-sm outline-none focus-visible:ring-2"
        />
        <Button size="sm" type="submit" disabled={!slug || taken || busy}>
          Lag
        </Button>
      </div>
      {slug && (
        <span className={cn('text-xs', taken ? 'text-bad' : 'text-muted-foreground')}>
          {taken ? 'Filen finnes allerede.' : `Lages som ${path} fra malen.`}
        </span>
      )}
    </form>
  )
}
