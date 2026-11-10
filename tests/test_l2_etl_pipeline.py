"""L2 ETL Pipeline - CRIT P0 Tests"""
import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etl.pipeline import ChunkStage, EnrichedDocument, ETLPipeline, ValidationStatus


@pytest.mark.parametrize('content', [
    'A' * 758 + '\n\n' + 'B' * 600,
    'first paragraph\n\n' + 'C' * 700,
    '   α🙂á' * 130 + '\n\n' + '日本語é ' * 130 + '  ',
    '\n\n' * 400 + 'text',
    '  leading and trailing  ',
])
def test_chunks_are_exact_source_slices_with_bounded_offsets(content):
    doc = EnrichedDocument('synthetic', 'title', content, [], [], 0, 'source', 'now')
    chunks = ChunkStage(chunk_size=500, overlap=50).chunk(doc)
    assert chunks
    for index, chunk in enumerate(chunks):
        assert chunk.chunk_index == index
        assert 0 <= chunk.start_offset < chunk.end_offset <= len(content)
        assert chunk.content == content[chunk.start_offset:chunk.end_offset]
        assert len(chunk.content) <= 500
    assert all(any(c.start_offset <= i < c.end_offset for c in chunks)
               for i, char in enumerate(content) if not char.isspace())


def test_long_paragraph_overlap_and_zero_overlap():
    doc = EnrichedDocument('synthetic', 'title', 'a' * 1200, [], [], 0, 'source', 'now')
    overlapping = ChunkStage(chunk_size=500, overlap=50).chunk(doc)
    assert [(c.start_offset, c.end_offset) for c in overlapping] == [(0, 500), (450, 950), (900, 1200)]
    disjoint = ChunkStage(chunk_size=500, overlap=0).chunk(doc)
    assert [(c.start_offset, c.end_offset) for c in disjoint] == [(0, 500), (500, 1000), (1000, 1200)]
    assert len({c.id for c in overlapping + disjoint}) > len(overlapping)
    assert overlapping[0].id == ChunkStage(chunk_size=500, overlap=50).chunk(doc)[0].id


def test_versioned_chunk_id_does_not_overwrite_legacy_row(tmp_path):
    from etl.pipeline import LoadStage
    doc = EnrichedDocument('stable-id', 'title', 'a' * 750, [], [], 0, 'source', 'now')
    db = tmp_path / 'legacy.sqlite'
    loader = LoadStage(str(db))
    with sqlite3.connect(db) as conn:
        conn.execute('INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                     ('chunk_stable-id_0', doc.id, 0, 'legacy citation', 0, 15, 2, '{}', 'past'))
    chunks = ChunkStage().chunk(doc)
    assert loader.load(chunks) == len(chunks)
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT content FROM chunks WHERE id=?', ('chunk_stable-id_0',)).fetchone()[0] == 'legacy citation'
        assert conn.execute('SELECT COUNT(*) FROM chunks').fetchone()[0] == len(chunks) + 1


@pytest.mark.parametrize('size,overlap', [(0, 0), (10, -1), (10, 10), (10, 11)])
def test_invalid_chunk_sizes_rejected(size, overlap):
    with pytest.raises(ValueError):
        ChunkStage(size, overlap)


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
        assert r.status == ValidationStatus.VALID
        assert r.chunks_created >= 2, f"Expected 2+ chunks, got {r.chunks_created}"
        conn = sqlite3.connect(pipeline.db_path)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT document_id FROM chunks")
        document_ids = [row[0] for row in cur.fetchall()]
        assert len(document_ids) == 1, f"Expected one ingested document, got {document_ids}"
        cur.execute(
            "SELECT start_offset, end_offset FROM chunks WHERE document_id=? ORDER BY chunk_index",
            (document_ids[0],),
        )
        chunks = cur.fetchall()
        conn.close()
        assert len(chunks) == r.chunks_created >= 2
        for i in range(len(chunks) - 1):
            assert chunks[i + 1][0] < chunks[i][1], f"No overlap {i}->{i + 1}"
