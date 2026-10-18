# Local verification - ADL UI Standard Pack 001

## Candidate identity

- Repository: `BAGO_AGENTIC_DATA_LAB`.
- Branch/base: `main`, HEAD and fetched `origin/main` both `f94811f7b186fec36f405403230f2d48d92dfb0c` (distance `0/0`).
- Changes remain uncommitted in the working tree.

## Changes

- `frontend/packages/bago-adl-ui-kit/components.tsx`: default `BagoButton` to `type="button"`; use a semantic selection button within the native data table, with accessible labels and pressed state.
- `frontend/packages/bago-adl-ui-kit/components.css` and `README.md`: focus/selection presentation and documented interaction behavior.
- `artifacts/bago-adl-ui-kit-0.1.0.zip`: regenerated from the six package files.
- `frontend/ui-kit-preview.html`, `frontend/src/ui-kit-preview.tsx`, and `frontend/src/ui-kit-preview.css`: repeatable local preview using actual kit source and fixture data.
- `frontend/vite.config.ts`: emit both the existing application and preview page.
- `frontend/tsconfig.json`: keep the app's existing `rootDir`; exclude the standalone Vite preview from the app's TypeScript build. The preview and kit were checked with separate no-emit TypeScript invocations.

## Verification

| Claim | Command or evidence | Result and scope |
|---|---|---|
| Repository aligned before work | `git rev-parse HEAD`; fetched `origin/main`; `git rev-list --left-right --count HEAD...origin/main` | HEAD and origin/main `f94811f7b186fec36f405403230f2d48d92dfb0c`; `0 0` |
| Package TypeScript source type-checks | `cd frontend && .\\node_modules\\.bin\\tsc.cmd --ignoreConfig --noEmit --jsx react-jsx --target ES2020 --module ESNext --moduleResolution bundler --esModuleInterop --skipLibCheck packages/bago-adl-ui-kit/components.tsx` | PASS |
| Preview TypeScript source type-checks | Same compiler flags with `--types vite/client src/ui-kit-preview.tsx` | PASS |
| Production frontend build emits both pages | `cd frontend && npm run build` | PASS; Vite transformed 127 modules and emitted `dist/index.html` and `dist/ui-kit-preview.html` |
| Browser renders at desktop and mobile | Playwright at `http://127.0.0.1:5173/ui-kit-preview.html`, 390x844 viewport; full-page captures at desktop and mobile | PASS; mobile `documentElement.scrollWidth` and viewport width both 390 px |
| Tab navigation and empty state | Clicked `Agent runs`, then `Policies` | PASS; table and “No local policies loaded” empty state rendered |
| Data grid selection | Clicked `Select row run-2047` in the Agent runs table | PASS; button exposes pressed/selected state and status announces `Selected run: run-2047` |
| Button default and explicit submit semantics | Clicked the no-type button inside a form, then `Explicit submit` | PASS; first increments its local action without submission; explicit submit changes count to 1 |
| Browser console | Playwright `console error` after navigation and interactions | PASS; 0 errors, 0 warnings |
| Package ZIP contents | Python `zipfile` comparison of entries and bytes | PASS; six entries match their package source files byte for byte |
| Generated README and full repository suite | `python scripts/generate_dynamic_readme.py` | PASS; 252 tests passed |
| README consistency | `python scripts/generate_dynamic_readme.py --check --skip-tests` | PASS; README verified, 252 cases collected without rerunning the suite |
| Whitespace and patch formatting | `git diff --check` | PASS on final working-tree diff |

## Artifact hashes (SHA-256)

- `frontend/packages/bago-adl-ui-kit/components.tsx`: `88af70b96fd6a9fc6ac25a8203a9cb0903493d83bfbb7b3a86f52e046469218a`
- `frontend/packages/bago-adl-ui-kit/components.css`: `ed2264e0f3236267dcc6c67e3a43344bbe7ae87b607f5a506562b093062dd691`
- `frontend/packages/bago-adl-ui-kit/README.md`: `47fe649959a367c3822dbba1bd545f57038b93c3e12bad126f2045ae965a0ed0`
- `artifacts/bago-adl-ui-kit-0.1.0.zip`: `493dd56d2bf10682da83085d38956a9a43aee63764f3371c98d50a43278bf497`
- `frontend/ui-kit-preview.html`: `c084a863862f499c69faf21ac0466fbe161f909db262d660d94506f07379ed04`
- `frontend/src/ui-kit-preview.tsx`: `06a955267d0280c914ac680558c39d65ed98dfa258a607e94aa372c12af60427`
- `frontend/src/ui-kit-preview.css`: `cf9283c08db777a16248a961f46887a0dc87114710a150e98eca3268ece61191`
- `frontend/vite.config.ts`: `0777f24f00cf662f15090b62ca6c81a7c3f074fd605f88a42fef2e7f9e97915c`
- `frontend/tsconfig.json`: `95e94938facdff54f6d82527601120268bb04ad58131e35ea4282635377c0242`

## Limits

- This preview uses local fixture data. No backend, provider, or authorization behavior is exercised.
- UI kit adoption by an existing production application screen remains `NOT_RUN`.
- Visual browser evidence was inspected; assistive-technology/screen-reader testing was `NOT_RUN`.
