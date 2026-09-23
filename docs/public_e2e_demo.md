# L13 · Public E2E demo

La demo pública es una sola ruta reproducible para ejecutar el bloque local
completo sin cuenta cloud, credenciales, Docker ni servicios de pago.

```text
Governed RAG
  → Ontology Engine
  → contexto LLM fixture
  → SandboxManager / LocalRestrictedBackend
  → pytest tipado
  → LocalTrace
  → eval determinista
```

## Requisitos

- Python 3.11+
- checkout del repositorio
- instalación local de `requirements.txt`

No se requiere AWS, OpenMetadata remoto, Docker ni red para ejecutar la demo.

## Ejecución

Desde la raíz del repositorio:

```bash
python -m pip install -r requirements.txt
python scripts/run_public_e2e_demo.py --check
python scripts/run_public_e2e_demo.py --write-evidence
```

`--check` no escribe artefactos y falla si el agente, la ontología, el sandbox
o el eval no terminan correctamente. `--write-evidence` genera
`evidence/public_e2e_demo.md` después de un resultado PASS.

## Alcance de la evidencia

La demo usa un grafo y corpus fixture comprometidos, un cliente
Bedrock-shaped inyectado y `LocalRestrictedBackend` con una request tipada de
pytest. Demuestra la composición y la trazabilidad local; no verifica AWS
live, OpenMetadata remoto, commercetools ni observabilidad de producción.

La misma cadena se ejecuta en `.github/workflows/ci.yml` junto con la suite,
la comprobación del README generado y `compileall`.
