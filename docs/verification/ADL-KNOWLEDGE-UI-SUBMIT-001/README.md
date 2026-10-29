# Chat resource submission repair

A resource dialog nested its form inside the chat composer. The fix renders the dialog outside the composer DOM and prevents React portal submit events from reaching the chat form.

A desktop test using synthetic input and Codex/gpt-6-luna observed exactly one knowledge request, no chat request, preserved unsent draft, a cited answer, and Escape restoring Resources focus. The pre-fix attempt reloaded the page. These are bounded observations, not a common-gateway or shared-index isolation claim.

See VERIFICATION.json and independent-review.json. Captures and model response contain only synthetic test data. Full required README generation and remote checks are recorded in CLOSURE.md when complete.

Do not reinterpret static source review, build success or model response as proof of production-wide authorization coverage.
