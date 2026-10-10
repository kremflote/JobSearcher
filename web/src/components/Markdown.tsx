import { Fragment, type ReactNode } from 'react'

/** Inline `**bold**` only. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  )
}

/**
 * Minimal Markdown for ad texts and company notes: paragraphs, `- ` lists and bold.
 * Anything else is shown as plain text. The F3 editor gets a full renderer.
 */
export function Markdown({ text, className }: { text: string; className?: string }) {
  const blocks = text.trim().split(/\n\s*\n/)
  return (
    <div className={className}>
      {blocks.map((block, b) => {
        const out: ReactNode[] = []
        let list: string[] = []
        let para: string[] = []
        const flushList = () => {
          if (list.length)
            out.push(
              <ul key={`l${out.length}`} className="my-1 list-disc pl-5">
                {list.map((li, i) => (
                  <li key={i}>{inline(li)}</li>
                ))}
              </ul>,
            )
          list = []
        }
        const flushPara = () => {
          if (para.length)
            out.push(
              <p key={`p${out.length}`}>
                {para.map((line, i) => (
                  <Fragment key={i}>
                    {i > 0 && <br />}
                    {inline(line)}
                  </Fragment>
                ))}
              </p>,
            )
          para = []
        }
        for (const line of block.split('\n')) {
          const m = /^\s*[-*]\s+(.*)$/.exec(line)
          if (m) {
            flushPara()
            list.push(m[1]!)
          } else {
            flushList()
            para.push(line)
          }
        }
        flushPara()
        flushList()
        return (
          <div key={b} className="mb-3 last:mb-0">
            {out}
          </div>
        )
      })}
    </div>
  )
}
