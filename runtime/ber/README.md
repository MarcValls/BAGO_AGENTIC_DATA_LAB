# BAGO Embedded Runtime bundle

This directory contains the source-derived BER `0.1.0` artifact and its lock.
ADL's `BerClient` verifies the pinned archive SHA-256, BER version, protocol,
source commit, and every packaged source file before extraction or startup.

The selected BAGO source is commit
`5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d`, version `4.11.10`. The artifact
was generated from a clean isolated worktree whose tracked source files were
modified for this BER candidate; the lock records `source_dirty_at_build: true`
and per-file hashes. The SHA-256 binds the package bytes but does not establish
publisher identity.

ADL does not start BER during import, app startup, or construction of a client.
Call `start()` explicitly, keep the JSON-lines child channel private to the ADL
process, and use the prepare/approve/execute sequence for effects. The shipped
profile enables `filesystem.read`, `filesystem.write`, `process.inspect`, and
typed `process.execute`; it blocks `filesystem.delete` and
`process.terminate`. ADL Agent Runner remains disabled pending its separate
parity, evidence, and standalone gates.
