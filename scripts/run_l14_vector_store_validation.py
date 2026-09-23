"""Validate the persistent local vector store and GovernedRAG integration."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
EVIDENCE_PATH = REPO_ROOT / "evidence" / "l14_vector_store.md"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metadata.schema import AuthorityLevel, ValidityStatus  # noqa: E402
from retrieval.governed_rag import GovernedRAG, RetrievalChunk, RetrievalMode  # noqa: E402
from retrieval.sqlite_vector_store import SQLiteVectorStore  # noqa: E402


QUERY = "¿Qué evidencia valida la política vigente?"


def build_chunks() -> list[RetrievalChunk]:
    return [
        RetrievalChunk(
            chunk_id="l14-policy-current",
            document_id="policy-v2",
            content="La política vigente sustituye la versión anterior.",
            title="Current policy",
            source_uri="docs/policy-v2.md",
            revision="2.0.0",
            authority=AuthorityLevel.VERIFIED,
            metadata={"asset_id": "policy-v2"},
        ),
        RetrievalChunk(
            chunk_id="l14-policy-old",
            document_id="policy-v1",
            content="La política anterior describe permisos históricos.",
            title="Old policy",
            source_uri="docs/policy-v1.md",
            revision="1.0.0",
            authority=AuthorityLevel.CANONICAL,
            validity=ValidityStatus.SUPERSEDED,
            metadata={"asset_id": "policy-v1"},
        ),
        RetrievalChunk(
            chunk_id="l14-policy-evidence",
            document_id="policy-receipt",
            content="La evidencia valida la política vigente.",
            title="Validation receipt",
            source_uri="evidence/policy-receipt.md",
            revision="1.0.0",
            authority=AuthorityLevel.VERIFIED,
            metadata={"asset_id": "policy-receipt"},
        ),
    ]


def run_validation() -> dict[str, Any]:
    chunks = build_chunks()
    with tempfile.TemporaryDirectory(prefix="bago-l14-vector-") as temporary:
        db_path = Path(temporary) / "vectors.db"
        store = SQLiteVectorStore(db_path)
        written = store.upsert(chunks)
        direct = store.search(QUERY, top_k=3)
        retriever = GovernedRAG.from_sqlite_vector_store(db_path)
        response = retriever.retrieve(
            QUERY,
            mode=RetrievalMode.SEMANTIC,
            top_k=2,
            rerank=False,
        )
        reloaded = SQLiteVectorStore(db_path)
        result = {
            "status": "PASS",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "local-persistent-sqlite-vector-index",
            "cost_usd": 0.0,
            "backend": direct.backend,
            "rows_written": written,
            "rows_indexed": store.count,
            "eligible_count": direct.eligible_count,
            "filtered_count": direct.filtered_count,
            "index_fingerprint": store.index_fingerprint,
            "fingerprint_stable_after_reload": store.index_fingerprint == reloaded.index_fingerprint,
            "direct_vector_citations": list(direct.citations),
            "governed_rag_hits": [hit.chunk.chunk_id for hit in response.hits],
            "governed_rag_citations": list(response.citations),
            "governed_rag_pipeline": list(response.pipeline),
            "superseded_excluded": "l14-policy-old" not in [hit.chunk.chunk_id for hit in response.hits],
            "aws_live": "NOT_RUN",
            "remote_vector_db": "NOT_RUN",
        }
    if not result["fingerprint_stable_after_reload"]:
        raise RuntimeError("L14 vector index fingerprint changed after reload")
    if not result["superseded_excluded"]:
        raise RuntimeError("L14 metadata gate admitted a superseded chunk")
    if result["rows_indexed"] != 3 or result["eligible_count"] != 2:
        raise RuntimeError(f"L14 unexpected index counts: {result}")
    if not result["governed_rag_hits"]:
        raise RuntimeError("L14 GovernedRAG returned no vector-backed hits")
    return result


def render_evidence(result: dict[str, Any]) -> str:
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    return f"""# L14 · Governed Local Vector Store

Generated at: `{result['generated_at']}`

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

- Status: `{result['status']}`
- Backend: `{result['backend']}`
- Rows indexed: `{result['rows_indexed']}`
- Eligible rows: `{result['eligible_count']}`
- Filtered rows: `{result['filtered_count']}`
- Fingerprint stable after reload: `{result['fingerprint_stable_after_reload']}`
- Superseded chunk excluded: `{result['superseded_excluded']}`
- Cost: `{result['cost_usd']:.1f} USD`
- AWS live: `{result['aws_live']}`
- Remote vector DB: `{result['remote_vector_db']}`

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
{encoded}
```
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail unless all L14 gates pass")
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help="write evidence/l14_vector_store.md after a passing run",
    )
    args = parser.parse_args(argv)
    result = run_validation()
    if args.write_evidence:
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(render_evidence(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.write_evidence:
        print(f"Evidence: {EVIDENCE_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
