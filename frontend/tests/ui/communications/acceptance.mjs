import { spawnSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
const root = fileURLToPath(new URL('../../../', import.meta.url))
const evidence = resolve(root, '../docs/whatsapp/evidence/W04')
mkdirSync(evidence, { recursive: true })
const checks = [
  ['fixtures', 'node_modules/vitest/vitest.mjs', 'run', 'tests/ui/communications', 'tests/ui/whatsapp'],
  ['typescript', 'node_modules/typescript/bin/tsc', '--noEmit', '--incremental', '--tsBuildInfoFile', resolve(evidence, 'typescript.tsbuildinfo')],
  ['build', 'node_modules/vite/bin/vite.js', 'build', '--outDir', resolve(evidence, 'build'), '--emptyOutDir'],
]
const results = checks.map(([id, ...args]) => {
  const result = spawnSync(process.execPath, args, { cwd: root, encoding: 'utf8', timeout: 120000 })
  process.stdout.write(result.stdout ?? ''); process.stderr.write(result.stderr ?? '')
  writeFileSync(resolve(evidence, `${id}.log`), `${result.stdout ?? ''}\n${result.stderr ?? ''}`, 'utf8')
  return { id, argv: [process.execPath, ...args], exit_code: result.status, error: result.error?.message ?? null, result: result.status === 0 ? 'PASS' : 'FAIL' }
})
const report = { status: results.every(item => item.result === 'PASS') ? 'PASS' : 'FAIL', scope: 'Offline fixture UI, TypeScript and production bundling; not live QR or sending', checks: results, live_browser: 'NOT_RUN: root owns visible Brave validation', live_send: 'NOT_RUN: no recipient authorized' }
writeFileSync(resolve(evidence, 'acceptance.json'), JSON.stringify(report, null, 2) + '\n')
console.log(JSON.stringify(report))
process.exitCode = report.status === 'PASS' ? 0 : 1
