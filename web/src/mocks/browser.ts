import { setupWorker } from 'msw/browser'
import { createMockDb } from './db'
import { isLlmState } from './fixtures/llm'
import { createHandlers } from './handlers'

/**
 * Starts MSW in the browser. `?mock_llm=<state>` on the URL the app is loaded with picks the
 * LLM usage variant (account, key_limit, unknown, unset, low, warn; fixtures/llm.ts).
 */
export async function startMockWorker() {
  const llmState = new URLSearchParams(window.location.search).get('mock_llm')
  const db = createMockDb(new Date(), isLlmState(llmState) ? { llmState } : {})
  const worker = setupWorker(...createHandlers(db))
  await worker.start({
    onUnhandledRequest: 'bypass',
    quiet: true,
  })
}
