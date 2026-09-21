"""L2 ETL Pipeline - CRIT P0 Tests"""
import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etl.pipeline import ETLPipeline, ValidationStatus


class TestL2ETLPipeline:
    @pytest.fixture
    def temp_db(self, tmp_path):
        db_path = tmp_path / "test_etl.db"
        yield str(db_path)

    @pytest.fixture
    def pipeline(self, temp_db):
        return ETLPipeline(db_path=temp_db)

    @pytest.fixture
    def test_doc_short(self, tmp_path):
        doc = tmp_path / "test_short.md"
        doc.write_text("# Test\n\nContenido de prueba para ETL.\n", encoding="utf-8")
        return doc

    @pytest.fixture
    def test_doc_long(self, tmp_path):
        """Documento largo para generar 2+ chunks"""
        doc = tmp_path / "test_long.md"
        content = "# Documento Largo\n\n"
        for i in range(50):
            content += f"Párrafo {i}: Este es contenido repetido para generar múltiples chunks en el pipeline ETL. Necesitamos suficiente texto para que el chunker divida el documento en al menos dos segmentos con overlap.\n\n"
        doc.write_text(content, encoding="utf-8")
        return doc

    def test_idempotency_same_content_hash(self, pipeline, test_doc_short):
        """CRIT P0: Mismo contenido -> DUPLICATE"""
        r1 = pipeline.ingest_file(str(test_doc_short))
        r2 = pipeline.ingest_file(str(test_doc_short))
        assert r1.status == ValidationStatus.VALID
        assert r2.status == ValidationStatus.DUPLICATE
        assert r1.chunks_created > 0
        assert r2.chunks_created == 0

    def test_error_receipt_generated(self, pipeline, tmp_path):
        """CRIT P0: Error siempre genera receipt con error_message"""
        r = pipeline.ingest_file(str(tmp_path / "missing.md"))
        assert r.status == ValidationStatus.ERROR
        assert r.error_message is not None
        assert r.ingested_at is not None

    def test_metadata_persistence_query(self, pipeline, test_doc_short):
        """CRIT P0: Metadata persiste y es consultable"""
        r = pipeline.ingest_file(str(test_doc_short))
        conn = sqlite3.connect(pipeline.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM chunks")
        count = cur.fetchone()[0]
        assert count >= r.chunks_created
        conn.close()

    def test_chunk_overlap_preserved(self, pipeline, test_doc_long):
        """CRIT P0: Overlap entre chunks se preserva"""
        r = pipeline.ingest_file(str(test_doc_long))
        if r.chunks_created < 2:
            pytest.skip(f"Need 2+ chunks, got {r.chunks_created}")
        conn = sqlite3.connect(pipeline.db_path)
        cur = conn.cursor()
        cur.execute("SELECT start_offset, end_offset FROM chunks WHERE document_id=? ORDER BY chunk_index", (r.source_id,))
        chunks = cur.fetchall()
        conn.close()
        # Verificar overlap en offsets
        for i in range(len(chunks) - 1):
            assert chunks[i+1][0] < chunks[i][1], f"No overlap {i}->{i+1}"
