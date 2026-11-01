import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config.ts'

// .bago/canon/DESKTOP_FIRST.md: preserve mobile tests, but do not execute
// them until the user explicitly requests mobile validation again.
const deferredMobileTitles = [
  'keeps compact mobile navigation scrollable and settings visible above the work area',
  'returns from mobile detail to the list with search and selected identity intact',
  'shows a directional navigation cue only while more content remains',
  'dismisses on outside click, resize and scroll, and clamps menu to viewport',
  'has effective hidden panels, full-width consumers and a scoped 320px-compatible horizontal navigation pattern',
  'keeps the full project panel open on narrow screens when requested open',
]
const escapedTitles = deferredMobileTitles.map(title => title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
// [\s\S] also preserves parameterized desktop tests containing line breaks.
const desktopTestNames = new RegExp(`^(?![\\s\\S]*(?:${escapedTitles.join('|')})$)[\\s\\S]*$`)

// TSX suites use Vitest. The .ts node:test contracts have a separate Node wrapper.
// Copied projects and generated artifacts do not extend this frontend test scope.
export default mergeConfig(viteConfig, defineConfig({
  test: {
    include: ['tests/**/*.test.tsx'],
    testNamePattern: desktopTestNames,
  },
}))
