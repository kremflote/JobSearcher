import { setupWorker } from 'msw/browser'
import { createHandlers } from './handlers'

export async function startMockWorker() {
  const worker = setupWorker(...createHandlers())
  await worker.start({
    onUnhandledRequest: 'bypass',
    quiet: true,
  })
}
