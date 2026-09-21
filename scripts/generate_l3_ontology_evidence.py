"""Generate reproducible L3 ontology evidence from the real domain model."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
OUTPUT_PATH = REPO_ROOT / "evidence" / "l3_ontology_graph.md"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metadata.ontology import (  # noqa: E402
    AuthorityLevel,
    ClassificationTag,
    KnowledgeAsset,
    KnowledgeChunk,
    KnowledgeGraph,
    OntologyRelation,
    RelationType,
    Source,
)


def build_evidence_graph() -> KnowledgeGraph:
    """Build a deterministic graph that exercises the L3 relationships."""
    graph = KnowledgeGraph()
    graph.sources["source_lab_contract"] = Source(
        source_id="source_lab_contract",
        uri="LAB_CONTRACT.md",
        source_type="FILE",
    )

    graph.add_asset(
        KnowledgeAsset(
            asset_id="asset_lab_contract",
            title="BAGO Lab Contract",
            description="Canonical laboratory boundary and governance contract.",
            asset_type="DOCUMENT",
            source_id="source_lab_contract",
            version="1.0.0",
            authority=AuthorityLevel.CANONICAL,
            classification=[ClassificationTag.CONTRACT],
        )
    )
    graph.add_asset(
        KnowledgeAsset(
            asset_id="claim_metadata_first",
            title="Metadata-first retrieval claim",
            description="Retrieval requires provenance and explicit authority metadata.",
            asset_type="CLAIM",
            source_id="source_lab_contract",
            authority=AuthorityLevel.PROPOSED,
            classification=[ClassificationTag.REQUIREMENT],
        )
    )
    graph.add_asset(
        KnowledgeAsset(
            asset_id="evidence_l3_tests",
            title="L3 ontology test evidence",
            description="Evidence produced by the CRIT P0 ontology test suite.",
            asset_type="EVIDENCE",
            source_id="source_lab_contract",
            authority=AuthorityLevel.VERIFIED,
            classification=[ClassificationTag.EVIDENCE, ClassificationTag.TEST],
        )
    )
    graph.add_chunk(
        KnowledgeChunk(
            chunk_id="chunk_contract_001",
            document_id="asset_lab_contract",
            chunk_index=0,
            content="Metadata-first retrieval requires provenance and authority.",
            start_offset=0,
            end_offset=61,
            word_count=7,
        )
    )

    graph.add_relation(
        OntologyRelation(
            relation_id="rel_claim_derived",
            relation_type=RelationType.DERIVED_FROM,
            source_id="claim_metadata_first",
            target_id="asset_lab_contract",
        )
    )
    graph.add_relation(
        OntologyRelation(
            relation_id="rel_chunk_belongs",
            relation_type=RelationType.BELONGS_TO,
            source_id="chunk_contract_001",
            target_id="asset_lab_contract",
        )
    )
    graph.add_relation(
        OntologyRelation(
            relation_id="rel_claim_references",
            relation_type=RelationType.REFERENCES,
            source_id="claim_metadata_first",
            target_id="chunk_contract_001",
        )
    )
    graph.add_relation(
        OntologyRelation(
            relation_id="rel_evidence_validates",
            relation_type=RelationType.VALIDATES,
            source_id="evidence_l3_tests",
            target_id="claim_metadata_first",
        )
    )
    return graph


def _node_id(prefix: str, value: str) -> str:
    """Return a Mermaid-safe node identifier."""
    safe_value = re.sub(r"[^A-Za-z0-9_]", "_", value)
    return f"{prefix}_{safe_value}"


def _label(value: str) -> str:
    """Escape a value for a Mermaid quoted label."""
    return value.replace('"', "'")


def render_mermaid(graph: KnowledgeGraph) -> str:
    """Render graph entities, provenance, and ontology relations as Mermaid."""
    node_lookup: dict[str, str] = {}
    lines = ["graph LR"]

    for source_id, source in sorted(graph.sources.items()):
        node = _node_id("source", source_id)
        node_lookup[source_id] = node
        lines.append(
            f'  {node}["Source<br/>{_label(source_id)}<br/>{_label(source.source_type)}"]'
        )

    for asset_id, asset in sorted(graph.assets.items()):
        node = _node_id("asset", asset_id)
        node_lookup[asset_id] = node
        lines.append(
            f'  {node}["KnowledgeAsset<br/>{_label(asset.title)}<br/>'
            f'{_label(asset.authority.value)} / {_label(asset.validity.value)}"]'
        )

    for chunk_id, chunk in sorted(graph.chunks.items()):
        node = _node_id("chunk", chunk_id)
        node_lookup[chunk_id] = node
        lines.append(
            f'  {node}["KnowledgeChunk<br/>{_label(chunk_id)}<br/>'
            f'index={chunk.chunk_index}"]'
        )

    for asset_id, asset in sorted(graph.assets.items()):
        if asset.source_id in node_lookup:
            lines.append(
                f"  {node_lookup[asset_id]} -.->|PROVENANCE| "
                f"{node_lookup[asset.source_id]}"
            )

    for relation in sorted(graph.relations, key=lambda item: item.relation_id):
        source_node = node_lookup[relation.source_id]
        target_node = node_lookup[relation.target_id]
        lines.append(
            f"  {source_node} -->|{relation.relation_type.value}| {target_node}"
        )

    lines.extend(
        [
            "  classDef source fill:#e8f1ff,stroke:#356ae6",
            "  classDef asset fill:#eaf7ea,stroke:#3d8b40",
            "  classDef chunk fill:#fff5dc,stroke:#b27b00",
            "  class source_source_lab_contract source",
            "  class asset_asset_lab_contract,asset_claim_metadata_first,"
            "asset_evidence_l3_tests asset",
            "  class chunk_chunk_contract_001 chunk",
        ]
    )
    return "\n".join(lines)


def render_evidence_document(graph: KnowledgeGraph) -> str:
    """Render the checked graph and its scope as a Markdown evidence receipt."""
    errors = graph.validate_integrity()
    if errors:
        raise ValueError("Cannot render invalid ontology graph: " + "; ".join(errors))

    lineage = " → ".join(graph.get_lineage("claim_metadata_first"))
    return f"""# L3 · Metadata & Ontology Evidence

This artifact is generated by `scripts/generate_l3_ontology_evidence.py` from
the classes in `src/metadata/ontology.py`. It is a deterministic representative
graph for the L3 contract, not a claim that the whole BAGO corpus is indexed.

## Integrity receipt

- Assets: {len(graph.assets)}
- Chunks: {len(graph.chunks)}
- Relations: {len(graph.relations)}
- Sources: {len(graph.sources)}
- `validate_integrity()`: `PASS` (0 errors)
- Claim lineage: `{lineage}`

## Ontology graph

```mermaid
{render_mermaid(graph)}
```

## Scope

The graph demonstrates source provenance, `DERIVED_FROM`, `BELONGS_TO`,
`REFERENCES`, and `VALIDATES`. The full test receipt remains the authoritative
verification for the behavior: `python -m pytest tests/ -q`.
"""


def main() -> None:
    graph = build_evidence_graph()
    document = render_evidence_document(graph)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(document, encoding="utf-8")
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(
        f"Graph: {len(graph.assets)} assets, {len(graph.chunks)} chunks, "
        f"{len(graph.relations)} relations, integrity PASS"
    )


if __name__ == "__main__":
    main()
