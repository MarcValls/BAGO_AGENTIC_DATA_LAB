# L14 · Governed local vector store

L14 añade un índice semántico persistente y local a la frontera de retrieval:

```text
RetrievalChunk + metadata
  → SQLiteVectorStore
  → metadata/authority/validity gate
  → deterministic hash vectors
  → GovernedRAG semantic response + EvidenceRef
```

## Ejecución

No requiere AWS, Docker, credenciales ni una base vectorial remota:

```bash
python -m pytest tests/test_sqlite_vector_store.py -q
python scripts/run_l14_vector_store_validation.py --check
python scripts/run_l14_vector_store_validation.py --write-evidence
```

`SQLiteVectorStore` conserva chunks, metadata y vectores en un SQLite local,
calcula un fingerprint estable y puede volver a conectarse a `GovernedRAG` tras
recargar el índice. La política de metadata se aplica antes de aceptar los
resultados; chunks `SUPERSEDED` no entran en el contexto por defecto.

## Límite

Es un backend local persistente y determinista para demostrar el contrato de
vector retrieval. No es una base vectorial distribuida, un servicio de
embeddings hospedado ni una medición de relevancia de producción. AWS y bases
vectoriales remotas siguen `NOT_RUN`.
