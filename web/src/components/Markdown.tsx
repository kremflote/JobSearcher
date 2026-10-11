import { Fragment, type ReactNode } from 'react'

/** Inline `**bold**` and `*italic*`. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? (
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : part.length > 2 && part.startsWith('*') && part.endsWith('*') ? (
      <em key={i}>{part.slice(1, -1)}</em>
    ) : (
      part
    ),
  )
}

/**
 * Minimal Markdown for ad texts, company notes and cover letters: paragraphs, `#` headings,
 * `- ` lists, bold and italic. Anything else is shown as plain text.
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
          const h = /^#{1,3}\s+(.*)$/.exec(line)
          if (h) {
            flushPara()
            flushList()
            out.push(
              <h3 key={`h${out.length}`} className="mb-1 font-semibold">
                {inline(h[1]!)}
              </h3>,
            )
            continue
          }
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
