# Independent static review — ChatTools SSR guard

Parent commit: `89c6069182633c316d46662a0182e7fba24d02e7` (PR99 initial candidate).
Reviewed source SHA-256: `64c855a132648f81dcc247cd3efbd0139df121ec1b800c939277b6c0d80ee108`.

**0 new P0, P1 or P2 findings observed in the one-line guard.**

At ChatTools.tsx:66, `typeof document !== 'undefined' && createPortal(...)` short-circuits before evaluating the portal and its document.body container when Node has no document. The remaining document accesses are in useEffect callbacks, which do not run during server rendering. The existing runtime/package-upgrade test actually calls react-dom/server.node renderToString(App), so this is restoration of an existing supported check. My earlier review note treating SSR as out of scope was too broad.

In a normal browser, the guard is true and the portal target, submit stopPropagation, modal state effect, close/cancel callback and launcher focus behavior are unchanged from parent89c6069. This is a static equivalence observation, not a dynamic browser check.

The source-only git diff --check returned exit code 0. No reviewer suite, build, browser or model execution occurred. The 17 focused tests and build PASS are implementer-provided results, not independently repeated. The prior model/browser response evidence applies to parent89c6069 only; it is not promoted to proof for this source hash. Follow-up native browser open/close evidence must be recorded separately.

No payload, provider selection, API, retrieval or authorization behavior is edited in this diff. Existing RAG isolation/permission concerns remain outside the fix. No checkout changes were made by the reviewer.
