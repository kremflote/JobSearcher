import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'
import { queryClient } from '@/api/queries'
import { ThemeProvider } from '@/lib/theme'
import { createRouter } from '@/routes'
import './index.css'

async function enableMocking() {
  if (import.meta.env.VITE_MOCK !== '1') return
  const { startMockWorker } = await import('./mocks/browser')
  await startMockWorker()
}

enableMocking().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={createRouter()} />
        </QueryClientProvider>
      </ThemeProvider>
    </StrictMode>,
  )
})
