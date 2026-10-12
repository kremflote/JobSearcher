import { Loader2 } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError } from '@/api/client'
import { saveProfileFile, useProfileTree, useStartDistill } from '@/api/queries'
import type { ApplicationCard } from '@/api/types'
import { Sheet } from '@/components/Sheet'
import { useToast } from '@/components/Toaster'
import { Button } from '@/components/ui/button'
import { slugify } from '@/features/profile/paths'

const TYPES = ['søknad', 'motivasjonsbrev', 'blogginnlegg', 'rapport', 'annet'] as const
const FOLDER = 'writing_samples'

/** "no" unless the text reads clearly more English than Norwegian. */
export function guessLanguage(text: string): 'no' | 'en' {
  const count = (re: RegExp) => (text.match(re) ?? []).length
  const no = count(/[æøå]|\b(og|jeg|er|ikke|som|med|på|til)\b/gi)
  const en = count(/\b(the|and|I|is|not|with|to|of)\b/g)
  return en > no * 1.5 ? 'en' : 'no'
}

/** `writing_samples/*.md` with the template's frontmatter; strings quoted (valid YAML). */
export function sampleFile(fields: { type: string; language: string; target: string; byMe: boolean; text: string }, now = new Date()) {
  const written = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  return [
    '---',
    `type: ${JSON.stringify(fields.type)}`,
    `language: ${fields.language}`,
    `written: ${JSON.stringify(written)}`,
    `target: ${JSON.stringify(fields.target)}`,
    'outcome: "ukjent"',
    `written_by_me: ${fields.byMe}`,
    '---',
    '',
    fields.text.trim(),
    '',
  ].join('\n')
}

/** A free path in `writing_samples/`: `<slug>.md`, else `<slug>-2.md`, … */
export function freePath(slug: string, taken: Set<string>) {
  const base = `${FOLDER}/${slug || 'skriveeksempel'}`
  for (let n = 1; ; n++) {
    const path = n === 1 ? `${base}.md` : `${base}-${n}.md`
    if (!taken.has(path)) return path
  }
}

/**
 * "Skriveeksempel" in the editor toolbar (FRONTEND §5.5): paste a text, save it as a writing
 * sample with the frontmatter filled in from the application, then redistill so `voice.md`
 * picks it up. Only voice changes, so jobs are not marked for rescoring (ARCHITECTURE §6.1).
 */
export function WritingSampleDialog({
  open,
  onOpenChange,
  card,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  card: ApplicationCard | undefined
}) {
  const qc = useQueryClient()
  const toast = useToast()
  const tree = useProfileTree()
  const distill = useStartDistill()
  const [text, setText] = useState('')
  const [type, setType] = useState<string>('søknad')
  const [language, setLanguage] = useState<'no' | 'en' | null>(null)
  const [target, setTarget] = useState<string | null>(null)
  const [byMe, setByMe] = useState(true)
  const [saving, setSaving] = useState(false)

  const defaultTarget = card ? `${card.job_title}, ${card.company}` : ''
  const lang = language ?? guessLanguage(text)
  const tgt = target ?? defaultTarget

  const reset = () => {
    setText('')
    setType('søknad')
    setLanguage(null)
    setTarget(null)
    setByMe(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      const taken = new Set((tree.data?.files ?? []).map((f) => f.path))
      const path = freePath(slugify(card ? `${card.company} ${card.job_title}` : 'skriveeksempel'), taken)
      await saveProfileFile(qc, path, sampleFile({ type, language: lang, target: tgt, byMe, text }), null)
      distill.mutate(undefined, {
        onError: () => toast({ message: 'Lagret, men kunne ikke oppdatere stemmeprofilen. Regenerer under Profil.' }),
      })
      toast({ message: `Lagret som ${path}. Stemmeprofilen oppdateres.` })
      reset()
      onOpenChange(false)
    } catch (e) {
      toast({ message: e instanceof ApiError ? e.message : 'Kunne ikke lagre skriveeksempelet.' })
    } finally {
      setSaving(false)
    }
  }

  const field = 'bg-background rounded-md border px-2 py-1.5 text-sm'
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Nytt skriveeksempel" side="right">
      <form
        className="flex flex-col gap-3 p-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (text.trim()) void save()
        }}
      >
        <p className="text-muted-foreground text-sm">
          Lim inn en tekst du har skrevet selv. Skriveagenten bruker skriveeksemplene til å lære stemmen din.
        </p>
        <textarea
          aria-label="Tekst"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={14}
          className={`${field} min-h-48 resize-y leading-relaxed`}
          placeholder="Lim inn teksten her"
        />
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1 text-xs font-medium">
            Type
            <select value={type} onChange={(e) => setType(e.target.value)} className={field}>
              {TYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium">
            Språk
            <select value={lang} onChange={(e) => setLanguage(e.target.value as 'no' | 'en')} className={field}>
              <option value="no">Norsk</option>
              <option value="en">Engelsk</option>
            </select>
          </label>
        </div>
        <label className="flex flex-col gap-1 text-xs font-medium">
          Stilling og bedrift
          <input value={tgt} onChange={(e) => setTarget(e.target.value)} className={field} />
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={byMe} onChange={(e) => setByMe(e.target.checked)} className="accent-primary mt-0.5 size-4" />
          <span>
            Skrevet av meg
            <span className="text-muted-foreground block text-xs">Fjern haken hvis teksten er sterkt redigert av AI eller andre.</span>
          </span>
        </label>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Avbryt
          </Button>
          <Button type="submit" disabled={!text.trim() || saving || !tree.data}>
            {saving && <Loader2 className="animate-spin" />} Lagre
          </Button>
        </div>
      </form>
    </Sheet>
  )
}
