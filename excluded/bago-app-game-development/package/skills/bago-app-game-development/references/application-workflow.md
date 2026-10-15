# Application workflow

Load this reference for material application design or implementation. Keep the existing platform and conventions unless the user asks to change them.

## Choose the slice

Identify the user, primary task, target platforms, important data, external services, and definition of done. Start with one end-to-end path through UI, domain logic, persistence or API, and a visible success/error result. Avoid scaffolding layers that the requested slice does not need.

## Platform concerns

- **Web:** route and state ownership, responsive layout, keyboard and screen-reader behavior, loading/empty/error states, API contracts, auth boundaries, browser support, and served bundle when live behavior is claimed.
- **Mobile:** navigation and lifecycle, offline/poor network, permissions, secure storage, screen sizes, accessibility, app signing, and the actual simulator/device target.
- **Desktop:** window and process lifecycle, filesystem scope, IPC boundaries, update/install behavior, operating-system integration, and packaged build identity.
- **CLI or service:** stable command/API contracts, validation, useful errors, logs without secrets, configuration precedence, and reproducible invocation.

Use the existing framework when present. For a new project, select a framework only after checking user constraints and the current environment. Do not turn a UI request into a backend rewrite or a feature request into a framework migration without evidence.

## Implementation review

Check that the visible control reaches the real capability and that success/error states reflect backend results. Check empty data, invalid input, failed network/provider, retry/cancel, and persistence where relevant. Keep credentials out of source, client bundles, logs, analytics, and ordinary local storage. Apply the repository's established security and accessibility patterns.

## Evidence

Use the narrowest existing checks that prove the requested behavior. A typecheck or build establishes only compilation/bundling. To claim the application works in a target environment, launch the exact artifact and inspect the relevant user path there. If the user named a live listener or deployed target, identify that runtime before editing or validating it.
