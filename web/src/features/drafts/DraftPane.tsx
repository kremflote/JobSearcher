import { Loader2 } from 'lucide-react'
import { useState } from 'react'
import { Markdown } from '@/components/Markdown'
import { Skeleton } from '@/components/ui/skeleton'
import { wordCount } from './diff'
import { Segmented } from './Segmented'

type Mode = 'edit' | 'preview'

/** Markdown text field with a preview tab and word count (FRONTEND §5.5). Read-only while the agent revises. */
export function DraftPane({
  text,
  onChange,
  revising,
}: {
  text: string | null
  onChange: (value: string) => void
  revising: boolean
}) {
  const [mode, setMode] = useState<Mode>('edit')
  if (text === null) return <Skeleton className="h-96 w-full" />
  return (
    <div className="flex flex-col gap-2">
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
        <span className="text-muted-foreground ml-auto text-xs tabular-nums" data-testid="word-count">
          {wordCount(text)} ord
        </span>
      </div>
      {revising && (
        <p className="text-muted-foreground flex items-center gap-1.5 text-sm" role="status">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Agenten jobber med meldingen din. Teksten er låst så lenge.
        </p>
      )}
      {mode === 'edit' ? (
        <textarea
          aria-label="Søknadstekst"
          value={text}
          readOnly={revising}
          onChange={(e) => onChange(e.target.value)}
          spellCheck
          lang="nb"
          className="border-input bg-background focus-visible:ring-ring field-sizing-content min-h-96 w-full resize-y rounded-md border px-3 py-2 font-serif text-base leading-relaxed outline-none read-only:opacity-60 focus-visible:ring-2"
        />
      ) : (
        <div className="min-h-96 rounded-md border px-4 py-3 font-serif leading-relaxed" data-testid="preview">
          <Markdown text={text} />
        </div>
      )}
    </div>
  )
}
