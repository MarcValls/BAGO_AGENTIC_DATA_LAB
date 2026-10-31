# Candidate rendered verification

Brave headless against the actual current React components and CSS in a dedicated verification entry. All API responses are explicitly synthetic and intercepted. This is component rendering and interaction evidence, not full App/Electron or production integration. The Browser plugin was attempted and returned `No browser is available`; the authorized standalone Playwright fallback was used.

Final main run: 11/11 assertions PASS, receipt `98ccf00681024ceeb38e1149a5f96579`. Context supplement: 4/4 PASS, receipt `35a082857d3444648f79e114d917e660`. No product source changes. Server 127.0.0.1:5197 and isolated headless browser were stopped by their owner after each run. No foreground window was requested.

Screenshot review inspected actual tasks desktop, provider lines desktop, models mobile and evaluation mobile. The first model-parent wrapper could clip the footer below the viewport; that was a harness defect, corrected in attempt03. Final models-mobile.png shows Guardar/Salir visible at the bottom while the model list scrolls separately. This does not assert the full application Settings parent layout.

Attempt01 FAIL was caused by two incorrect harness assumptions: i18n changes document.title and current provider status line uses a 3px ::after rather than borderBottom. Both earlier reports/receipts are retained unchanged. Attempt02 PASS is preserved with its later-discovered harness-clipping qualification. Do not present either failure as a source defect or hide them.

One generic HTTP404 resource console entry remains in the main report while the missing-document fixture is exercised. No uncaught page errors or Vite overlays occurred. No completely-clear-console claim is made.

The per-goal matrix records precise criteria, PASS/PARTIAL and NOT_RUN limits. Square/color remains PARTIAL because the original eight-screen set was not fully exercised. Model policy enforcement and saved-task durability require backend regression evidence. Context filesystem reads require backend integration evidence. Root owns these gates and the acceptance decision.
