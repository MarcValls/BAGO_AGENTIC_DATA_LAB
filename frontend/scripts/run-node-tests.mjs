import { realpathSync } from 'node:fs'
import { spawnSync } from 'node:child_process'

const root = realpathSync.native(process.cwd())
const child = spawnSync(process.execPath, ['--test', ...process.argv.slice(2)], { cwd: root, stdio: 'inherit' })
if (child.error) {
  console.error(child.error.message)
  process.exitCode = 1
} else {
  process.exitCode = child.status ?? 1
}
