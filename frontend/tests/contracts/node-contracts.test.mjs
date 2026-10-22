import { after, describe } from 'node:test'
import { createServer } from 'vite'

// Run with cwd frontend. Vite resolves the contracts' existing extensionless TS
// imports; node:test remains the owner of their assertions and exit status.
describe('Node TypeScript contracts through Vite SSR', async () => {
  const server = await createServer({
    server: { middlewareMode: true },
    appType: 'custom',
  })
  after(async () => { await server.close() })

  for (const path of [
    '/tests/contracts/action/action.test.ts',
    '/tests/contracts/evidence/evidence.test.ts',
    '/tests/contracts/trace/trace.test.ts',
  ]) {
    await server.ssrLoadModule(path)
  }
})
