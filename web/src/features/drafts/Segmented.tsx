import { cn } from '@/lib/utils'

/** Segmented control (tabs) for the editor: Rediger/Forhåndsvis, and Utkast/Chat/Versjoner on mobile. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  className,
}: {
  value: T
  options: readonly { value: T; label: string }[]
  onChange: (value: T) => void
  label: string
  className?: string
}) {
  return (
    <div role="tablist" aria-label={label} className={cn('bg-muted inline-flex rounded-lg p-0.5', className)}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn(
            'h-7 flex-1 rounded-md px-3 text-sm whitespace-nowrap transition-colors',
            'focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none',
            o.value === value ? 'bg-background text-foreground font-medium shadow-sm' : 'text-muted-foreground',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
