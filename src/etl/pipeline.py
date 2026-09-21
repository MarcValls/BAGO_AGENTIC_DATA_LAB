"""
L2 · ETL Pipeline — Ingestión Gobernada de Documentación

Pipeline:
SOURCE → EXTRACT → NORMALIZE → VALIDATE → ENRICH → CHUNK → METADATA → LOAD → VERIFY

Principio crítico: Todo documento ingerido genera receipt con evidence.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Any
import requests
from bs4 import BeautifulSoup
import markdown


# ============================================================================
# DOMAIN MODEL
# ============================================================================

class SourceType(str, Enum):
    FILE = "FILE"
    WEB = "WEB"
    API = "API"
    MANUAL = "MANUAL"


class ValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    DUPLICATE = "DUPLICATE"
    ERROR = "ERROR"


@dataclass
class SourceDocument:
    """Documento fuente antes de procesar."""
    id: str
    source_type: SourceType
    location: str  # URL or file path
    raw_content: str
    fetched_at: str
    content_hash: str
    
    @staticmethod
    def compute_hash(content: str) -> str:
        """SHA-256 hash del contenido."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:32]


@dataclass
class NormalizedDocument:
    """Documento normalizado a schema unificado."""
    id: str
    title: str
    content: str
    format: str  # 'markdown', 'text', 'html'
    source_id: str
    normalized_at: str


@dataclass
class EnrichedDocument:
    """Documento enriquecido con metadata extraída."""
    id: str
    title: str
    content: str
    entities: List[str]
    keywords: List[str]
    word_count: int
    source_id: str
    enriched_at: str


@dataclass
class DocumentChunk:
    """Chunk semántico de documento."""
    id: str
    document_id: str
    chunk_index: int
    content: str
    start_offset: int
    end_offset: int
    word_count: int
    embedding: Optional[List[float]]  # L4: embeddings reales
    metadata: Dict[str, Any]


@dataclass
class IngestionReceipt:
    """Receipt de ingestión con evidencia."""
    receipt_id: str
    source_id: str
    status: ValidationStatus
    chunks_created: int
    metadata: Dict[str, Any]
    ingested_at: str
    duration_ms: int
    error_message: Optional[str] = None
    evidence_refs: List[str] = None


# ============================================================================
# ETL STAGES
# ============================================================================

class ExtractStage:
    """Stage 1: Extracción de fuentes heterogéneas."""
    
    def extract_from_file(self, file_path: str) -> SourceDocument:
        """Extrae contenido de archivo local."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")
        
        content = path.read_text(encoding='utf-8')
        content_hash = SourceDocument.compute_hash(content)
        
        return SourceDocument(
            id=f"file_{path.stem}_{content_hash[:8]}",
            source_type=SourceType.FILE,
            location=str(path.absolute()),
            raw_content=content,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            content_hash=content_hash
        )
    
    def extract_from_web(self, url: str) -> SourceDocument:
        """Extrae contenido de URL web."""
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        content = response.text
        content_hash = SourceDocument.compute_hash(content)
        
        return SourceDocument(
            id=f"web_{hashlib.md5(url.encode()).hexdigest()[:8]}_{content_hash[:8]}",
            source_type=SourceType.WEB,
            location=url,
            raw_content=content,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            content_hash=content_hash
        )


class NormalizeStage:
    """Stage 2: Normalización a schema unificado."""
    
    def normalize(self, source: SourceDocument) -> NormalizedDocument:
        """Normaliza contenido a Markdown unificado."""
        content = source.raw_content
        
        # Si es HTML, convertir a Markdown
        if source.source_type == SourceType.WEB:
            soup = BeautifulSoup(content, 'html.parser')
            # Extraer título
            title = soup.find('title')
            title_text = title.string if title else "Untitled"
            # Convertir body a texto
            content = soup.get_text(separator='\n', strip=True)
        else:
            title = f"Document {source.id}"
        
        # Detectar formato
        if content.strip().startswith('#'):
            doc_format = 'markdown'
        elif '<' in content and '>' in content:
            doc_format = 'html'
        else:
            doc_format = 'text'
        
        return NormalizedDocument(
            id=f"norm_{source.id}",
            title=title,
            content=content,
            format=doc_format,
            source_id=source.id,
            normalized_at=datetime.now(timezone.utc).isoformat()
        )


class ValidateStage:
    """Stage 3: Validación de schema y deduplicación."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inicializa base de datos de hashes para deduplicación."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_hashes (
                content_hash TEXT PRIMARY KEY,
                document_id TEXT,
                ingested_at TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def validate(self, doc: NormalizedDocument, source: SourceDocument) -> ValidationStatus:
        """Valida documento y detecta duplicados."""
        # Check 1: Schema validation
        if not doc.content or len(doc.content.strip()) == 0:
            return ValidationStatus.INVALID_SCHEMA
        
        # Check 2: Duplicate detection por content hash
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT document_id FROM document_hashes WHERE content_hash = ?',
            (source.content_hash,)
        )
        existing = cursor.fetchone()
        conn.close()
        
        if existing:
            return ValidationStatus.DUPLICATE
        
        return ValidationStatus.VALID
    
    def register_hash(self, doc: NormalizedDocument, source: SourceDocument):
        """Registra hash para futura deduplicación."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO document_hashes VALUES (?, ?, ?)',
            (source.content_hash, doc.id, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()


class EnrichStage:
    """Stage 4: Enriquecimiento con entity extraction."""
    
    def enrich(self, doc: NormalizedDocument) -> EnrichedDocument:
        """Extrae entidades y keywords."""
        content = doc.content
        
        # Entity extraction simple (en producción usar NLP)
        entities = []
        if 'BAGO' in content:
            entities.append('BAGO')
        if 'LangGraph' in content:
            entities.append('LangGraph')
        if 'Python' in content:
            entities.append('Python')
        
        # Keyword extraction (frecuencia de términos)
        words = content.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 3 and word not in ['the', 'and', 'for', 'with']:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        keywords = sorted(word_freq.keys(), key=lambda w: word_freq[w], reverse=True)[:10]
        
        return EnrichedDocument(
            id=f"enrich_{doc.id}",
            title=doc.title,
            content=doc.content,
            entities=entities,
            keywords=keywords,
            word_count=len(words),
            source_id=doc.source_id,
            enriched_at=datetime.now(timezone.utc).isoformat()
        )


class ChunkStage:
    """Stage 5: Chunking semántico."""
    
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk(self, doc: EnrichedDocument) -> List[DocumentChunk]:
        """Divide documento en chunks semánticos."""
        content = doc.content
        chunks = []
        
        # Split por párrafos (simplificado)
        paragraphs = content.split('\n\n')
        
        current_chunk = ""
        current_start = 0
        chunk_index = 0
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < self.chunk_size:
                current_chunk += para + '\n\n'
            else:
                # Crear chunk actual
                if current_chunk.strip():
                    chunk = DocumentChunk(
                        id=f"chunk_{doc.id}_{chunk_index}",
                        document_id=doc.id,
                        chunk_index=chunk_index,
                        content=current_chunk.strip(),
                        start_offset=current_start,
                        end_offset=current_start + len(current_chunk),
                        word_count=len(current_chunk.split()),
                        embedding=None,  # L4: embeddings reales
                        metadata={
                            'entities': doc.entities,
                            'keywords': doc.keywords[:3]
                        }
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                
                # Nuevo chunk con overlap
                current_start += len(current_chunk) - self.overlap
                current_chunk = current_chunk[-self.overlap:] + para + '\n\n'
        
        # Último chunk
        if current_chunk.strip():
            chunk = DocumentChunk(
                id=f"chunk_{doc.id}_{chunk_index}",
                document_id=doc.id,
                chunk_index=chunk_index,
                content=current_chunk.strip(),
                start_offset=current_start,
                end_offset=len(content),
                word_count=len(current_chunk.split()),
                embedding=None,
                metadata={
                    'entities': doc.entities,
                    'keywords': doc.keywords[:3]
                }
            )
            chunks.append(chunk)
        
        return chunks


class LoadStage:
    """Stage 6: Carga en vector store + metadata DB."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inicializa base de datos de chunks."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT,
                chunk_index INTEGER,
                content TEXT,
                start_offset INTEGER,
                end_offset INTEGER,
                word_count INTEGER,
                metadata_json TEXT,
                ingested_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_document_id ON chunks(document_id)
        ''')
        conn.commit()
        conn.close()
    
    def load(self, chunks: List[DocumentChunk]) -> int:
        """Carga chunks en base de datos."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        loaded_count = 0
        for chunk in chunks:
            try:
                cursor.execute(
                    '''INSERT OR REPLACE INTO chunks 
                       (id, document_id, chunk_index, content, start_offset, 
                        end_offset, word_count, metadata_json, ingested_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (chunk.id, chunk.document_id, chunk.chunk_index,
                     chunk.content, chunk.start_offset, chunk.end_offset,
                     chunk.word_count, json.dumps(chunk.metadata),
                     datetime.now(timezone.utc).isoformat())
                )
                loaded_count += 1
            except Exception as e:
                print(f"Error loading chunk {chunk.id}: {e}")
        
        conn.commit()
        conn.close()
        
        return loaded_count


# ============================================================================
# ETL PIPELINE ORCHESTRATOR
# ============================================================================

class ETLPipeline:
    """Orquestador del pipeline ETL completo."""
    
    def __init__(self, db_path: str = "etl_metadata.db"):
        self.extract = ExtractStage()
        self.normalize = NormalizeStage()
        self.validate = ValidateStage(db_path)
        self.enrich = EnrichStage()
        self.chunk = ChunkStage()
        self.load = LoadStage(db_path)
        self.db_path = db_path
    
    def ingest_file(self, file_path: str) -> IngestionReceipt:
        """Ingiere archivo individual."""
        start_time = datetime.now(timezone.utc)
        
        try:
            # Stage 1: Extract
            source = self.extract.extract_from_file(file_path)
            
            # Stage 2: Normalize
            normalized = self.normalize.normalize(source)
            
            # Stage 3: Validate
            status = self.validate.validate(normalized, source)
            
            if status != ValidationStatus.VALID:
                return IngestionReceipt(
                    receipt_id=f"receipt_{source.id}",
                    source_id=source.id,
                    status=status,
                    chunks_created=0,
                    metadata={'error': f'Validation failed: {status.value}'},
                    ingested_at=start_time.isoformat(),
                    duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                    error_message=f"Document validation failed: {status.value}"
                )
            
            # Register hash para deduplicación futura
            self.validate.register_hash(normalized, source)
            
            # Stage 4: Enrich
            enriched = self.enrich.enrich(normalized)
            
            # Stage 5: Chunk
            chunks = self.chunk.chunk(enriched)
            
            # Stage 6: Load
            loaded_count = self.load.load(chunks)
            
            # Generate receipt
            receipt = IngestionReceipt(
                receipt_id=f"receipt_{source.id}",
                source_id=source.id,
                status=ValidationStatus.VALID,
                chunks_created=loaded_count,
                metadata={
                    'title': normalized.title,
                    'word_count': enriched.word_count,
                    'entities': enriched.entities,
                    'keywords': enriched.keywords[:5]
                },
                ingested_at=start_time.isoformat(),
                duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                evidence_refs=[f"chunks:{loaded_count}"]
            )
            
            return receipt
            
        except Exception as e:
            return IngestionReceipt(
                receipt_id=f"receipt_error_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                source_id=file_path,
                status=ValidationStatus.ERROR,
                chunks_created=0,
                metadata={'error': str(e)},
                ingested_at=start_time.isoformat(),
                duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                error_message=str(e)
            )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("L2 · ETL PIPELINE — DOCUMENT INGESTION")
    print("=" * 80)
    
    # Initialize pipeline
    pipeline = ETLPipeline(db_path="l2_etl_metadata.db")
    
    # Ingest documents from command line or use defaults
    if len(sys.argv) > 1:
        files_to_ingest = sys.argv[1:]
    else:
        # Default: ingest lab documentation
        files_to_ingest = [
            "LAB_CONTRACT.md",
            "ARCHITECTURE.md",
            "ROADMAP.md"
        ]
    
    receipts = []
    total_chunks = 0
    
    for file_path in files_to_ingest:
        print(f"\nIngesting: {file_path}")
        receipt = pipeline.ingest_file(file_path)
        receipts.append(receipt)
        
        if receipt.status == ValidationStatus.VALID:
            print(f"  ✅ Status: {receipt.status.value}")
            print(f"  📄 Chunks created: {receipt.chunks_created}")
            print(f"  ⏱️  Duration: {receipt.duration_ms}ms")
            total_chunks += receipt.chunks_created
        else:
            print(f"  ❌ Status: {receipt.status.value}")
            print(f"  ⚠️  Error: {receipt.error_message}")
    
    print("\n" + "=" * 80)
    print("INGESTION SUMMARY")
    print("=" * 80)
    print(f"Documents processed: {len(receipts)}")
    print(f"Successfully ingested: {sum(1 for r in receipts if r.status == ValidationStatus.VALID)}")
    print(f"Total chunks created: {total_chunks}")
    print(f"Duplicates skipped: {sum(1 for r in receipts if r.status == ValidationStatus.DUPLICATE)}")
    print(f"Errors: {sum(1 for r in receipts if r.status == ValidationStatus.ERROR)}")
    print("=" * 80)
