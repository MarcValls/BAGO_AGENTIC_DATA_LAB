# Local verification — CRIT-ADL-SKILLS-001-RETEST-1

## CI diagnosis

The GitHub Actions run [38608531292](https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB/actions/runs/38608531292)
ran commit `a066792f4ad878ded812cda0220fc1a4c0925289` on Ubuntu 24.04 / Python
3.11. Its dependency installation succeeded, including `Pillow==12.2.0`.
All three failures in `tests/test_render_portfolio_demo_video.py` reported
`FAIL: ffmpeg not available`. The CI workflow now installs `ffmpeg` before
pytest, and a regression test checks that ordering.

## L2 ETL

`tests/test_l2_etl_pipeline.py::TestL2ETLPipeline::test_chunk_overlap_preserved`
no longer skips when the receipt reports fewer than two chunks. It asserts
`VALID`, requires at least two created chunks, obtains the actual persisted
`document_id` from SQLite, requires the stored row count to match the receipt,
and checks every adjacent offset pair overlaps.

## L4 retrieval

The benchmark uses 32 labelled documents (including hard negatives) and nine
queries, reporting Recall@1, Recall@3, Precision@k and MRR@k for lexical,
deterministic hash-semantic and hybrid retrieval with reranking on/off. It
reports 24 configurations. The canonical-governance filter is scored against
the four queries with relevant evidence that survives that policy; excluded
labels are not counted as retrieval misses.

Observed all-current aggregate: Hybrid Recall@3 100.0% / MRR@3 87.0%; lexical
88.9% / 81.5%; deterministic semantic 72.2% / 66.7%. This is a constructed,
offline baseline with a hash-feature semantic backend. It does not establish
generalization, statistical significance, production embedding quality or
professional proficiency.

## Competency reporting

`.bago/canon/JOB_SKILL_MATRIX.md` now describes Hybrid retrieval, ETL and Data
pipelines as locally implemented while stating each tested scope and remaining
limitations. `README.md` was regenerated from that source; it displays the same
three entries.

## Executed checks

- `python scripts/generate_dynamic_readme.py` — exit 0; full suite recorded as
  248 passing tests.
- `python scripts/generate_dynamic_readme.py --check --skip-tests` — PASS,
  README reports 248 tests.
- `python -m pytest tests/test_l2_etl_pipeline.py tests/test_retrieval_benchmark.py tests/test_dynamic_readme.py -q` — 12 passed.
- `git diff --check` — PASS.

GitHub Actions for the candidate commit is still `NOT_RUN`; this goal remains
`PREPARED` until the candidate workflow run is observed.
