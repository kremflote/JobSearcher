import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { saveDraft } from '@/api/queries'
import type { Draft } from '@/api/types'

export type SaveState = 'saved' | 'dirty' | 'saving' | 'error'

/** Autosave delay after the last keystroke (FRONTEND §5.5). */
export const AUTOSAVE_MS = 2000

/**
 * Editor text with autosave (FRONTEND §5.5). The text follows the newest version while there are
 * no unsaved edits, so a finished revision replaces it. Edits are saved 2 s after the last
 * keystroke as a user version based on the version they were made from (`baseId`).
 */
export function useDraftEditor(applicationId: number, latest: Draft | undefined) {
  const qc = useQueryClient()
  const [text, setText] = useState<string | null>(null)
  const [baseId, setBaseId] = useState<number | null>(null)
  const [state, setState] = useState<SaveState>('saved')
  const textRef = useRef<string | null>(null)
  const baseRef = useRef<number | null>(null)
  const stateRef = useRef<SaveState>('saved')
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const inFlight = useRef<Promise<void> | null>(null)

  const update = useCallback((s: SaveState) => {
    stateRef.current = s
    setState(s)
  }, [])

  // Load the newest version when there is nothing unsaved.
  useEffect(() => {
    if (!latest || stateRef.current !== 'saved' || latest.id === baseRef.current) return
    textRef.current = latest.content
    baseRef.current = latest.id
    setText(latest.content)
    setBaseId(latest.id)
  }, [latest])

  const flush = useCallback(async (): Promise<void> => {
    clearTimeout(timer.current)
    if (inFlight.current) await inFlight.current
    if (stateRef.current !== 'dirty' && stateRef.current !== 'error') return
    const content = textRef.current ?? ''
    update('saving')
    const run = (async () => {
      try {
        const draft = await saveDraft(qc, applicationId, content, baseRef.current)
        baseRef.current = draft.id
        setBaseId(draft.id)
        if (textRef.current === content) update('saved')
        else {
          update('dirty')
          timer.current = setTimeout(() => void flush(), AUTOSAVE_MS)
        }
      } catch {
        update('error')
      }
    })()
    inFlight.current = run
    await run
    inFlight.current = null
  }, [qc, applicationId, update])

  const edit = useCallback(
    (value: string) => {
      textRef.current = value
      setText(value)
      if (stateRef.current !== 'saving') update('dirty')
      clearTimeout(timer.current)
      timer.current = setTimeout(() => void flush(), AUTOSAVE_MS)
    },
    [flush, update],
  )

  /** Replaces the text with an older version and saves it right away (Gjenopprett). */
  const restore = useCallback(
    async (version: Draft) => {
      textRef.current = version.content
      baseRef.current = version.id
      setText(version.content)
      setBaseId(version.id)
      update('dirty')
      await flush()
    },
    [flush, update],
  )

  // Save on leaving the editor; warn when closing the tab with unsaved text.
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (stateRef.current !== 'saved') e.preventDefault()
    }
    window.addEventListener('beforeunload', warn)
    return () => {
      window.removeEventListener('beforeunload', warn)
      if (stateRef.current === 'dirty') void flush()
    }
  }, [flush])

  return { text, baseId, state, edit, flush, restore }
}
