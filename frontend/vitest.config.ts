import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config.ts'

// TSX suites use Vitest. The .ts node:test contracts have a separate Node wrapper.
// Copied projects and generated artifacts do not extend this frontend test scope.
export default mergeConfig(viteConfig, defineConfig({
  test: {
    include: ['tests/**/*.test.tsx'],
  },
}))
