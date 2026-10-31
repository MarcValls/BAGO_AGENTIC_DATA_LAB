# Finite evidence publication — closed snapshot

Main and frontend runtime snapshots are CLOSED / VALIDATED_SCOPED_TASK. Final independent review, CLOSE, acceptance and the applied original audit reconciliation are included. This is scoped closure; global product closure is not claimed.

Run `python verify_publication.py` from this directory or pass `--root`; verification uses Path(__file__) and portable published-relative paths, without Windows paths or live runtimes. PUBLICATION_INDEX.json maps original paths to raw payloads, including unchanged visual/review bindings. Raw-to-Git mappings record exact byte identity or explicit CRLF/LF equivalence; Linux used Git archive blobs, Windows/frontend checks used raw worktree bytes. Historical before-repair sources were recovered from Git8065906 only when the exact previously recorded raw SHA matched; current sources were not edited. The original audit is APPLIED_VERIFIED; its copies remain preserved.

Excluded: node_modules, caches, build/dist, browser profiles, temporary fixtures and Docker Config/Env dumps. Secret scans of selected text emit no values; explicit fixtures are distinguished from unresolved candidates. Checksum PASS does not itself establish product behavior or authority. No ZIP is required for this finite package; an optional local ZIP may wrap the final allowlist.
