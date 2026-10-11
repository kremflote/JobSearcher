import { ArrowLeft } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router'
import { useProfileTree } from '@/api/queries'
import { Page } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useIsWide } from '@/lib/useMediaQuery'
import { DerivedStatus, DerivedView } from './DerivedPanel'
import { FileEditor } from './FileEditor'
import { FileTree } from './FileTree'

/**
 * Profil (FRONTEND §5.6). `/profil/<path>` opens a file, `/profil?vis=destillert` the derived
 * profile. From 1024 px the file list stays on the left; below that the list and the open file
 * are separate screens.
 */
export function ProfilePage() {
  const tree = useProfileTree()
  const wide = useIsWide()
  const splat = useParams()['*'] ?? ''
  const path = splat ? splat.split('/').map(decodeURIComponent).join('/') : null
  const [params] = useSearchParams()
  const derived = !path && params.get('vis') === 'destillert'
  const detail = path !== null || derived

  return (
    <Page title="Profil">
      {tree.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : tree.isError ? (
        <div className="text-sm">
          <p className="text-muted-foreground mb-2">Kunne ikke hente profilen.</p>
          <Button size="sm" variant="outline" onClick={() => tree.refetch()}>
            Prøv igjen
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <DerivedStatus outdated={tree.data.derived_outdated} madeAt={tree.data.derived_at} />
          <div className="flex gap-6">
            {(wide || !detail) && (
              <aside className={wide ? 'w-64 shrink-0' : 'w-full'}>
                <FileTree files={tree.data.files} folders={tree.data.folders} selected={path} derivedSelected={derived} />
              </aside>
            )}
            {(wide || detail) && (
              <div className="min-w-0 flex-1">
                {path !== null ? (
                  <FileEditor path={path} showBack={!wide} />
                ) : derived ? (
                  <>
                    {!wide && (
                      <Button size="sm" variant="ghost" className="mb-2 -ml-2" asChild>
                        <Link to="/profil">
                          <ArrowLeft /> Profilfiler
                        </Link>
                      </Button>
                    )}
                    <DerivedView files={tree.data.files} />
                  </>
                ) : (
                  <p className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
                    Velg en fil til venstre. Agentene leser disse filene; etter endringer regenererer du den destillerte
                    profilen.
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </Page>
  )
}
