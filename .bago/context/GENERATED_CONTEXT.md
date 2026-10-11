# Generated context bridge

The installed BAGO scanner currently writes generated index data to ignored `.gabo/context/`, outside tracked project context. This repository migration does not modify that external writer.

Treat `.gabo/context/` as a disposable retrieval cache only. Durable instructions and authority live at `.bago/INDEX.md`; pre-migration generated-file fingerprints are recorded in `.bago/migrations/context-unification-20261011/reference-snapshot.json`. Regenerate the cache using the configured BAGO context behavior.
