"""L3 · Metadata & Ontology - CRIT P0 Tests"""

import pytest
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from metadata.ontology import (
    KnowledgeGraph,
    KnowledgeAsset,
    KnowledgeChunk,
    Source,
    Revision,
    OntologyRelation,
    RelationType,
    AuthorityLevel,
    ClassificationTag,
)


class TestL3Ontology:
    """Suite CRIT P0 para L3 · Metadata & Ontology"""

    @pytest.fixture
    def empty_graph(self):
        """Grafo vacío para tests"""
        return KnowledgeGraph()

    @pytest.fixture
    def sample_asset(self):
        """Asset de ejemplo"""
        return KnowledgeAsset(
            asset_id="asset_001",
            title="Test Asset",
            description="Asset de prueba para ontología",
            asset_type="DOCUMENT",
            source_id="source_001",
            version="1.0.0",
            authority=AuthorityLevel.PROPOSED,
            classification=[ClassificationTag.ARCHITECTURE],
        )

    @pytest.fixture
    def sample_chunk(self):
        """Chunk de ejemplo"""
        return KnowledgeChunk(
            chunk_id="chunk_001",
            document_id="doc_001",
            chunk_index=0,
            content="Contenido de prueba para el chunk",
            start_offset=0,
            end_offset=100,
            word_count=15,
        )

    def test_add_asset_to_graph(self, empty_graph, sample_asset):
        """CRIT P0: Añadir asset al grafo"""
        empty_graph.add_asset(sample_asset)

        assert "asset_001" in empty_graph.assets
        assert empty_graph.assets["asset_001"].title == "Test Asset"

    def test_add_chunk_to_graph(self, empty_graph, sample_chunk):
        """CRIT P0: Añadir chunk al grafo"""
        empty_graph.add_chunk(sample_chunk)

        assert "chunk_001" in empty_graph.chunks
        assert empty_graph.chunks["chunk_001"].word_count == 15

    def test_add_relation(self, empty_graph, sample_asset):
        """CRIT P0: Añadir relación entre entidades"""
        empty_graph.add_asset(sample_asset)

        # Crear segundo asset
        asset2 = KnowledgeAsset(
            asset_id="asset_002",
            title="Derived Asset",
            description="Derivado del primero",
            asset_type="CHUNK",
            source_id="source_001",
        )
        empty_graph.add_asset(asset2)

        # Crear relación DERIVED_FROM
        relation = OntologyRelation(
            relation_id="rel_001",
            relation_type=RelationType.DERIVED_FROM,
            source_id="asset_002",
            target_id="asset_001",
        )
        empty_graph.add_relation(relation)

        assert len(empty_graph.relations) == 1
        assert empty_graph.relations[0].relation_type == RelationType.DERIVED_FROM

    def test_lineage_tracking(self, empty_graph):
        """CRIT P0: Lineage tracking correcto"""
        # Crear cadena: asset_c <- asset_b <- asset_a
        for i, name in enumerate(["asset_a", "asset_b", "asset_c"]):
            asset = KnowledgeAsset(
                asset_id=name,
                title=name,
                description=f"Asset {i}",
                asset_type="DOCUMENT",
                source_id="source_001",
            )
            empty_graph.add_asset(asset)

        # Añadir relaciones DERIVED_FROM
        empty_graph.add_relation(OntologyRelation(
            relation_id="rel_ab",
            relation_type=RelationType.DERIVED_FROM,
            source_id="asset_b",
            target_id="asset_a",
        ))
        empty_graph.add_relation(OntologyRelation(
            relation_id="rel_bc",
            relation_type=RelationType.DERIVED_FROM,
            source_id="asset_c",
            target_id="asset_b",
        ))

        lineage = empty_graph.get_lineage("asset_c")

        assert len(lineage) == 3
        assert "asset_c" in lineage
        assert "asset_b" in lineage
        assert "asset_a" in lineage

    def test_superseded_chain(self, empty_graph):
        """CRIT P0: Cadena de versiones superseded"""
        # Crear versión 1.0.0
        v1 = KnowledgeAsset(
            asset_id="doc_v1",
            title="Document v1",
            description="Versión 1",
            asset_type="DOCUMENT",
            source_id="source_001",
            version="1.0.0",
        )
        empty_graph.add_asset(v1)

        # Crear versión 2.0.0 que supersede a v1
        v2 = KnowledgeAsset(
            asset_id="doc_v2",
            title="Document v2",
            description="Versión 2",
            asset_type="DOCUMENT",
            source_id="source_001",
            version="2.0.0",
        )
        empty_graph.add_asset(v2)

        # Marcar v1 como superseded por v2
        v1.mark_superseded("doc_v2")

        chain = empty_graph.get_superseded_chain("doc_v1")

        assert len(chain) == 2
        assert "doc_v1" in chain
        assert "doc_v2" in chain

    def test_filter_by_authority(self, empty_graph):
        """CRIT P0: Filtrar por autoridad"""
        # Añadir assets con diferentes autoridades
        for auth in [AuthorityLevel.CANONICAL, AuthorityLevel.VERIFIED, AuthorityLevel.PROPOSED]:
            asset = KnowledgeAsset(
                asset_id=f"asset_{auth.value}",
                title=f"Asset {auth.value}",
                description="Test",
                asset_type="DOCUMENT",
                source_id="source_001",
                authority=auth,
            )
            empty_graph.add_asset(asset)

        canonical_assets = empty_graph.filter_by_authority(AuthorityLevel.CANONICAL)

        assert len(canonical_assets) == 1
        assert canonical_assets[0].authority == AuthorityLevel.CANONICAL

    def test_filter_by_classification(self, empty_graph):
        """CRIT P0: Filtrar por clasificación"""
        asset1 = KnowledgeAsset(
            asset_id="asset_arch",
            title="Architecture Doc",
            description="Documento de arquitectura",
            asset_type="DOCUMENT",
            source_id="source_001",
            classification=[ClassificationTag.ARCHITECTURE, ClassificationTag.REQUIREMENT],
        )
        asset2 = KnowledgeAsset(
            asset_id="asset_test",
            title="Test Spec",
            description="Especificación de tests",
            asset_type="DOCUMENT",
            source_id="source_001",
            classification=[ClassificationTag.TEST],
        )
        empty_graph.add_asset(asset1)
        empty_graph.add_asset(asset2)

        arch_assets = empty_graph.filter_by_classification(ClassificationTag.ARCHITECTURE)

        assert len(arch_assets) == 1
        assert arch_assets[0].asset_id == "asset_arch"

    def test_validate_integrity_no_errors(self, empty_graph, sample_asset):
        """CRIT P0: Validar integridad sin errores"""
        empty_graph.add_asset(sample_asset)

        errors = empty_graph.validate_integrity()

        assert len(errors) == 0

    def test_validate_integrity_broken_relation(self, empty_graph):
        """CRIT P0: Detectar relación rota"""
        # Crear relación que referencia asset inexistente
        relation = OntologyRelation(
            relation_id="rel_broken",
            relation_type=RelationType.REFERENCES,
            source_id="nonexistent_source",
            target_id="nonexistent_target",
        )
        empty_graph.add_relation(relation)

        errors = empty_graph.validate_integrity()

        assert len(errors) > 0
        assert "nonexistent_source" in errors[0] or "nonexistent_target" in errors[0]

    def test_validate_integrity_no_cycles(self, empty_graph):
        """CRIT P0: Detectar ciclos en lineage"""
        # Crear ciclo: a <- b <- a
        asset_a = KnowledgeAsset(
            asset_id="cycle_a",
            title="A",
            description="Cycle A",
            asset_type="DOCUMENT",
            source_id="source_001",
        )
        asset_b = KnowledgeAsset(
            asset_id="cycle_b",
            title="B",
            description="Cycle B",
            asset_type="DOCUMENT",
            source_id="source_001",
        )
        empty_graph.add_asset(asset_a)
        empty_graph.add_asset(asset_b)

        # Crear ciclo
        empty_graph.add_relation(OntologyRelation(
            relation_id="rel_1",
            relation_type=RelationType.DERIVED_FROM,
            source_id="cycle_b",
            target_id="cycle_a",
        ))
        empty_graph.add_relation(OntologyRelation(
            relation_id="rel_2",
            relation_type=RelationType.DERIVED_FROM,
            source_id="cycle_a",
            target_id="cycle_b",
        ))

        errors = empty_graph.validate_integrity()

        assert len(errors) > 0
        assert "Cycle" in errors[0] or "cycle" in errors[0]

    def test_source_content_hash(self):
        """CRIT P0: Content hash para idempotencia"""
        source = Source(
            source_id="src_001",
            uri="test://document.md",
            source_type="FILE",
        )

        content = "Test content for hashing"
        hash1 = source.content_hash(content)
        hash2 = source.content_hash(content)
        hash3 = source.content_hash("Different content")

        assert hash1 == hash2  # Mismo contenido = mismo hash
        assert hash1 != hash3  # Diferente contenido = diferente hash
        assert len(hash1) == 64  # SHA-256 hex = 64 caracteres

    def test_revision_tracking(self, empty_graph, sample_asset):
        """CRIT P0: Tracking de revisiones"""
        empty_graph.add_asset(sample_asset)

        revision = Revision(
            revision_id="rev_001",
            asset_id="asset_001",
            revision_number="1.0.1",
            change_summary="Fixed typo in description",
            changed_by="test_user",
            evidence_refs=["evidence_001"],
        )

        assert revision.revision_number == "1.0.1"
        assert revision.changed_by == "test_user"
        assert len(revision.evidence_refs) == 1
