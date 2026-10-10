import { Search, SlidersHorizontal, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Sheet } from '@/components/Sheet'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  activeFilterCount,
  MIN_SCORE_OPTIONS,
  ROLE_OPTIONS,
  SORT_OPTIONS,
  SOURCE_OPTIONS,
  STATUS_OPTIONS,
  TYPE_TABS,
  type JobFilters,
} from './filters'

type Props = { filters: JobFilters; setFilters: (patch: Partial<JobFilters>) => void; reset: () => void }

export function TypeTabs({ filters, setFilters }: Pick<Props, 'filters' | 'setFilters'>) {
  return (
    <div role="tablist" aria-label="Jobbtype" className="no-scrollbar flex gap-1 overflow-x-auto px-3 py-2">
      {TYPE_TABS.map((t) => {
        const selected = filters.type === t.value
        return (
          <button
            key={t.label}
            role="tab"
            aria-selected={selected}
            onClick={() => setFilters({ type: t.value })}
            className={cn(
              'h-7 shrink-0 rounded-full px-3 text-sm transition-colors',
              selected ? 'bg-primary text-primary-foreground' : 'bg-secondary text-secondary-foreground hover:bg-accent',
            )}
          >
            {t.label}
          </button>
        )
      })}
    </div>
  )
}

/** Free-text search, written to the URL 300 ms after the last keystroke. */
function SearchInput({ value, onChange, className }: { value: string; onChange: (q: string) => void; className?: string }) {
  const [text, setText] = useState(value)
  useEffect(() => setText(value), [value])
  useEffect(() => {
    if (text === value) return
    const t = setTimeout(() => onChange(text), 300)
    return () => clearTimeout(t)
  }, [text]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <label className={cn('relative block', className)}>
      <span className="sr-only">Søk i jobber</span>
      <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2" aria-hidden />
      <input
        type="search"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Søk tittel, bedrift, sted"
        className="border-input bg-background focus-visible:ring-ring/50 h-8 w-full rounded-md border pr-2 pl-8 text-sm outline-none focus-visible:ring-[3px]"
      />
    </label>
  )
}

function Select<T extends string | number>({
  label,
  value,
  options,
  onChange,
  emptyLabel,
}: {
  label: string
  value: T | null
  options: { value: T; label: string }[]
  onChange: (v: T | null) => void
  emptyLabel?: string
}) {
  return (
    <label className="flex flex-col gap-1 text-xs md:flex-row md:items-center md:gap-0">
      <span className="text-muted-foreground md:sr-only">{label}</span>
      <select
        aria-label={label}
        value={value === null ? '' : String(value)}
        onChange={(e) => {
          const raw = e.target.value
          const opt = options.find((o) => String(o.value) === raw)
          onChange(opt ? opt.value : null)
        }}
        className="border-input bg-background focus-visible:ring-ring/50 h-9 rounded-md border px-2 text-sm outline-none focus-visible:ring-[3px] md:h-8"
      >
        {emptyLabel && <option value="">{emptyLabel}</option>}
        {options.map((o) => (
          <option key={String(o.value)} value={String(o.value)}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function Fields({ filters, setFilters }: Pick<Props, 'filters' | 'setFilters'>) {
  return (
    <>
      <Select
        label="Status"
        value={filters.status}
        options={STATUS_OPTIONS}
        onChange={(v) => setFilters({ status: v ?? 'ny' })}
      />
      <Select
        label="Min. score"
        value={filters.min_score}
        options={MIN_SCORE_OPTIONS.map((n) => ({ value: n, label: `Score ≥ ${n}` }))}
        onChange={(v) => setFilters({ min_score: v })}
        emptyLabel="Alle scorer"
      />
      <Select label="Kilde" value={filters.source} options={SOURCE_OPTIONS} onChange={(v) => setFilters({ source: v })} emptyLabel="Alle kilder" />
      <Select label="Rolle" value={filters.role} options={ROLE_OPTIONS} onChange={(v) => setFilters({ role: v })} emptyLabel="Alle roller" />
      <label className="flex flex-col gap-1 text-xs md:flex-row md:items-center md:gap-1.5">
        <span className="text-muted-foreground">Frist før</span>
        <input
          type="date"
          aria-label="Frist før"
          value={filters.deadline_before ?? ''}
          onChange={(e) => setFilters({ deadline_before: e.target.value || null })}
          className="border-input bg-background focus-visible:ring-ring/50 h-9 rounded-md border px-2 text-sm outline-none focus-visible:ring-[3px] md:h-8"
        />
      </label>
      <Select label="Sortering" value={filters.sort} options={SORT_OPTIONS.map((o) => ({ ...o, label: `Sorter: ${o.label.toLowerCase()}` }))} onChange={(v) => setFilters({ sort: v ?? 'deadline' })} />
    </>
  )
}

/** PC (≥ 768 px): filters as a row above the list. */
export function FilterRow({ filters, setFilters, reset }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 border-b px-3 pb-2" data-testid="filter-row">
      <SearchInput value={filters.q} onChange={(q) => setFilters({ q })} className="w-full" />
      <Fields filters={filters} setFilters={setFilters} />
      {activeFilterCount(filters) > 0 && (
        <Button size="sm" variant="ghost" onClick={reset}>
          <X /> Nullstill
        </Button>
      )}
    </div>
  )
}

/** Mobile: search in the header, everything else in a bottom sheet. */
export function FilterSheetButton({ filters, setFilters, reset }: Props) {
  const [open, setOpen] = useState(false)
  const count = activeFilterCount(filters)
  return (
    <>
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)} aria-label={`Filtre${count ? ` (${count} aktive)` : ''}`}>
        <SlidersHorizontal />
        {count > 0 && <span className="bg-primary text-primary-foreground rounded-full px-1.5 text-[10px]">{count}</span>}
      </Button>
      <Sheet open={open} onOpenChange={setOpen} title="Filtre">
        <div className="flex flex-col gap-3">
          <SearchInput value={filters.q} onChange={(q) => setFilters({ q })} />
          <Fields filters={filters} setFilters={setFilters} />
          <div className="mt-1 flex gap-2">
            <Button variant="outline" className="flex-1" onClick={reset}>
              Nullstill
            </Button>
            <Button className="flex-1" onClick={() => setOpen(false)}>
              Vis jobber
            </Button>
          </div>
        </div>
      </Sheet>
    </>
  )
}
