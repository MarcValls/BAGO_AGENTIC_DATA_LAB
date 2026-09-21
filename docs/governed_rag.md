# Governed RAG · L4

`GovernedRAG` separa recuperación de generación y ejecución. Su flujo es:

```text
query
  → intent classification
  → metadata / authority / validity gate
  → lexical BM25-like retrieval
  → deterministic semantic baseline
  → hybrid score fusion
  → optional deterministic reranking
  → evidence-ready context
```

## Boundary

El retriever sólo propone contexto. No llama a un proveedor, no ejecuta
efectos materiales y no concede permisos. Los chunks `SUPERSEDED`, `INVALID`
y `DEPRECATED` quedan fuera de la política por defecto; la autoridad mínima,
el dominio, la fecha y la procedencia se pueden declarar mediante
`MetadataFilter`.

Cada `RetrievalHit` conserva `chunk_id`, `document_id`, `source_uri`,
`revision`, los scores lexical/semantic/fused y un `EvidenceRef` listo para
una cita en el contexto.

## Offline semantic baseline

El backend incluido es `HashEmbedding`: combina tokens y character n-grams en
un vector hash determinista. Esto permite tests y benchmark sin descargar un
modelo ni llamar a una API. Es una interfaz reemplazable, no una afirmación de
calidad semántica de producción.

## L2 adapter

`load_sqlite_chunks("l2_etl_metadata.db")` adapta las filas L2 a
`RetrievalChunk`. Como la tabla L2 todavía no contiene autoridad ontológica
completa, el adapter conserva la fila como `PROPOSED`, usa `CURRENT` y genera
una referencia de procedencia `etl://<document_id>`; una futura integración
con el catálogo L3 puede sustituir esos campos por metadata canónica.

## Commands

```powershell
# Tests específicos de L4
python -m pytest tests/test_retrieval_accuracy.py tests/test_retrieval_benchmark.py -q

# Benchmark reproducible
python scripts/benchmark_retrieval.py
```

El resultado se escribe en `evidence/retrieval_benchmark_results.md` y cubre
BM25-like, semantic hash, hybrid, reranking on/off, top-k 10/25/50/100 y
filtros `all-current` frente a `canonical-governance`.
