"""Contract tests for the public L3 metadata schema module."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from metadata.schema import (  # noqa: E402
    AuthorityLevel,
    ClassificationTag,
    KnowledgeAsset,
    KnowledgeChunk,
    Revision,
    Source,
    ValidityStatus,
)


def test_schema_entities_expose_governance_metadata():
    asset = KnowledgeAsset(
        asset_id="asset_schema",
        title="Schema contract",
        description="Public L3 entity contract",
        asset_type="DOCUMENT",
        source_id="source_schema",
        authority=AuthorityLevel.VERIFIED,
        classification=[ClassificationTag.CONTRACT],
    )

    assert asset.version == "1.0.0"
    assert asset.authority is AuthorityLevel.VERIFIED
    assert asset.classification == [ClassificationTag.CONTRACT]
    assert asset.validity is ValidityStatus.CURRENT
    assert asset.superseded_by is None


def test_schema_chunk_serializes_without_losing_metadata():
    chunk = KnowledgeChunk(
        chunk_id="chunk_schema",
        document_id="asset_schema",
        chunk_index=2,
        content="schema content",
        start_offset=10,
        end_offset=24,
        word_count=2,
        keywords=["schema"],
        entities=["KnowledgeAsset"],
    )

    serialized = chunk.to_dict()

    assert serialized["chunk_id"] == "chunk_schema"
    assert serialized["keywords"] == ["schema"]
    assert serialized["entities"] == ["KnowledgeAsset"]


def test_schema_source_and_revision_support_provenance():
    source = Source(
        source_id="source_schema",
        uri="LAB_CONTRACT.md",
        source_type="FILE",
    )
    revision = Revision(
        revision_id="revision_schema",
        asset_id="asset_schema",
        revision_number="1.0.1",
        change_summary="Added schema contract tests",
        changed_by="test_user",
        evidence_refs=["evidence_l3_tests"],
    )

    assert len(source.content_hash("stable content")) == 64
    assert revision.asset_id == "asset_schema"
    assert revision.evidence_refs == ["evidence_l3_tests"]


def test_superseding_an_asset_updates_validity():
    asset = KnowledgeAsset(
        asset_id="asset_v1",
        title="Version 1",
        description="Initial version",
        asset_type="DOCUMENT",
        source_id="source_schema",
    )

    asset.mark_superseded("asset_v2")

    assert asset.superseded_by == "asset_v2"
    assert asset.validity is ValidityStatus.SUPERSEDED
