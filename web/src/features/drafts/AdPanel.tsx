import { ExternalLink } from 'lucide-react'
import { useJob } from '@/api/queries'
import { Markdown } from '@/components/Markdown'
import { Skeleton } from '@/components/ui/skeleton'
import { adUrl } from '@/features/jobs/JobDetail'

/** Our stored ad text beside the letter (FRONTEND §5.5, wide PC only). */
export function AdPanel({ jobId }: { jobId: number }) {
  const job = useJob(jobId)
  const url = job.data ? adUrl(job.data) : null
  return (
    <section aria-label="Annonse" data-testid="ad-panel" className="flex flex-col gap-3 p-4">
      <div className="flex items-baseline gap-2">
        <h2 className="text-sm font-semibold">Annonse</h2>
        {url && (
          <a href={url} target="_blank" rel="noreferrer" className="text-primary ml-auto inline-flex items-center gap-1 text-xs underline-offset-4 hover:underline">
            Se annonsen <ExternalLink className="size-3" aria-hidden />
          </a>
        )}
      </div>
      {job.isPending ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </div>
      ) : job.isError ? (
        <p className="text-muted-foreground text-sm">Kunne ikke hente annonsen.</p>
      ) : job.data.description ? (
        <Markdown text={job.data.description} className="text-sm leading-relaxed" />
      ) : (
        <p className="text-muted-foreground text-sm">Bare tittel kjent.</p>
      )}
    </section>
  )
}
