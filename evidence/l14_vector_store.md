# L14 · Governed Local Vector Store

Generated at: `2026-09-23T15:26:30.402350+00:00`

This zero-cost validation persists deterministic semantic vectors in SQLite and
connects the stored backend to `GovernedRAG` without changing the authorization
boundary:

```text
RetrievalChunk + metadata
  → SQLite vector index
  → metadata/authority/validity gate
  → semantic scores
  → GovernedRAG evidence-ready response
```

## Result

- Status: `PASS`
- Backend: `sqlite_hash_vector`
- Rows indexed: `3`
- Eligible rows: `2`
- Filtered rows: `1`
- Fingerprint stable after reload: `True`
- Superseded chunk excluded: `True`
- Cost: `0.0 USD`
- AWS live: `NOT_RUN`
- Remote vector DB: `NOT_RUN`

## Reproduce

```bash
python -m pytest tests/test_sqlite_vector_store.py -q
python scripts/run_l14_vector_store_validation.py --check
python scripts/run_l14_vector_store_validation.py --write-evidence
```

## Boundary

The backend is a persistent local SQLite index using the existing deterministic
hash embedding. It demonstrates persistence, reload stability, semantic
scoring, metadata filtering and evidence citations. It is not a distributed
vector database, a hosted embedding service or a production relevance claim.

## Stable summary

```json
{
  "aws_live": "NOT_RUN",
  "backend": "sqlite_hash_vector",
  "cost_usd": 0.0,
  "direct_vector_citations": [
    "evidence/policy-receipt.md#revision=1.0.0",
    "docs/policy-v2.md#revision=2.0.0"
  ],
  "eligible_count": 2,
  "filtered_count": 1,
  "fingerprint_stable_after_reload": true,
  "generated_at": "2026-09-23T15:26:30.402350+00:00",
  "governed_rag_citations": [
    "evidence/policy-receipt.md#revision=1.0.0",
    "docs/policy-v2.md#revision=2.0.0"
  ],
  "governed_rag_hits": [
    "l14-policy-evidence",
    "l14-policy-current"
  ],
  "governed_rag_pipeline": [
    "intent_classification",
    "metadata_filters",
    "semantic_embedding",
    "authority_validity_gate",
    "evidence_context_ready"
  ],
  "index_fingerprint": "7b13b311121198f5773d697daf5b9776988af59dfbaabc61c97f0029c7a9b7d6",
  "remote_vector_db": "NOT_RUN",
  "rows_indexed": 3,
  "rows_written": 3,
  "scope": "local-persistent-sqlite-vector-index",
  "status": "PASS",
  "superseded_excluded": true
}
```
