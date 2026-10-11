import { Bot, Check, Loader2, Send } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import type { DraftMessage, DraftSummary, Task } from '@/api/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { fmtVersionTime } from './Versions'

const SUGGESTIONS = ['Gjør den kortere', 'Mer formell tone', 'Mer konkret om prosjektene mine']

/** A sent message: `stored` once the server has it (it is then in `messages`). */
export type PendingRevision = { instruction: string; stored: boolean; task: Task | undefined }

/**
 * Chat with the revision agent (FRONTEND §5.5): the stored messages, plus the user's own edits
 * from the version list. Sending starts a background task that either answers in the chat or
 * ends in a new version, linked from the reply.
 */
export function RevisionChat({
  messages,
  versions,
  pending,
  onSend,
  onSelectVersion,
  onSaveRule,
  disabled,
  className,
}: {
  messages: DraftMessage[]
  versions: DraftSummary[]
  pending: PendingRevision | null
  onSend: (instruction: string) => void
  onSelectVersion: (id: number) => void
  onSaveRule: (messageId: number) => void
  disabled: boolean
  className?: string
}) {
  const [text, setText] = useState('')
  const end = useRef<HTMLLIElement>(null)
  const busy = !!pending && (!pending.task || pending.task.status === 'queued' || pending.task.status === 'running')
  const failed = pending?.task && (pending.task.status === 'failed' || pending.task.status === 'cancelled')

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end' })
  }, [messages.length, versions.length, pending?.instruction, busy])

  const send = (instruction: string) => {
    const value = instruction.trim()
    if (!value || busy || disabled) return
    onSend(value)
    setText('')
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    send(text)
  }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(text)
    }
  }

  return (
    <section aria-label="Revisjonschat" data-testid="revision-chat" className={cn('flex min-h-0 flex-col', className)}>
      <ol className="flex flex-1 flex-col gap-2 overflow-y-auto p-3 text-sm">
        {history(messages, versions).map((item) =>
          'role' in item ? (
            <li key={`m${item.id}`} className="contents">
              {item.role === 'user' ? (
                <UserBubble text={item.text} />
              ) : (
                <AgentBubble>
                  <span className="whitespace-pre-wrap">{item.text}</span>
                  {item.draft_id && (
                    <>
                      {' '}
                      <button
                        type="button"
                        className="text-primary underline-offset-4 hover:underline"
                        onClick={() => onSelectVersion(item.draft_id!)}
                      >
                        Versjon {versions.find((v) => v.id === item.draft_id)?.version ?? ''}
                      </button>
                    </>
                  )}
                  {item.style_rule && <StyleRule message={item} onSave={() => onSaveRule(item.id)} />}
                </AgentBubble>
              )}
            </li>
          ) : (
            <li key={`v${item.id}`} className="text-muted-foreground self-center text-xs">
              Du redigerte · versjon {item.version} · {fmtVersionTime(item.created_at)}
            </li>
          ),
        )}
        {pending && (busy || failed) && (
          <li className="contents">
            {!pending.stored && <UserBubble text={pending.instruction} />}
            <AgentBubble>
              {busy ? (
                <span className="text-muted-foreground flex items-center gap-1.5" role="status">
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                  {pending.task?.message ?? 'Sender …'}
                </span>
              ) : (
                <span className="text-bad">
                  {pending.task?.status === 'cancelled' ? 'Avbrutt.' : `Feilet: ${pending.task?.message ?? 'ukjent feil'}`}
                </span>
              )}
            </AgentBubble>
          </li>
        )}
        <li ref={end} aria-hidden />
      </ol>

      <form
        onSubmit={submit}
        className={cn(
          'bg-background flex flex-col gap-2 border-t p-3',
          'sticky bottom-[calc(3.5rem+env(safe-area-inset-bottom))] md:bottom-0',
        )}
      >
        <div className="flex flex-wrap gap-1">
          {SUGGESTIONS.map((s) => (
            <Button key={s} type="button" size="xs" variant="outline" disabled={busy || disabled} onClick={() => send(s)}>
              {s}
            </Button>
          ))}
        </div>
        <div className="flex items-end gap-2">
          <textarea
            aria-label="Instruksjon til agenten"
            placeholder="Hva skal endres?"
            rows={2}
            value={text}
            disabled={disabled}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKey}
            className="border-input bg-background focus-visible:ring-ring min-h-10 flex-1 resize-none rounded-md border px-3 py-2 text-base outline-none focus-visible:ring-2 md:text-sm"
          />
          <Button type="submit" size="icon" aria-label="Send" disabled={!text.trim() || busy || disabled}>
            {busy ? <Loader2 className="animate-spin" /> : <Send />}
          </Button>
        </div>
      </form>
    </section>
  )
}

/** Messages and the user's own versions, oldest first (stable for equal times). */
function history(messages: DraftMessage[], versions: DraftSummary[]): (DraftMessage | DraftSummary)[] {
  return [...messages, ...versions.filter((v) => v.author === 'user')].sort((a, b) =>
    a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0,
  )
}

/** A rule the reviser suggests for all letters; saving appends it to style_overrides.md. */
function StyleRule({ message, onSave }: { message: DraftMessage; onSave: () => void }) {
  return (
    <div className="bg-background mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border px-2 py-1.5">
      <span className="flex-1 basis-40">
        <span className="text-muted-foreground text-xs">Stilregel for alle brev: </span>
        {message.style_rule}
      </span>
      {message.style_rule_saved ? (
        <span className="text-muted-foreground flex items-center gap-1 text-xs">
          <Check className="size-3.5" aria-hidden />
          Lagret
        </span>
      ) : (
        <Button type="button" size="xs" variant="outline" onClick={onSave}>
          Lagre som stilregel
        </Button>
      )}
    </div>
  )
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="bg-primary text-primary-foreground max-w-[85%] self-end rounded-lg rounded-br-sm px-3 py-1.5 whitespace-pre-wrap">
      {text}
    </div>
  )
}

function AgentBubble({ children }: { children: ReactNode }) {
  return (
    <div className="bg-muted flex max-w-[85%] items-start gap-1.5 self-start rounded-lg rounded-bl-sm px-3 py-1.5">
      <Bot className="text-muted-foreground mt-0.5 size-3.5 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  )
}
