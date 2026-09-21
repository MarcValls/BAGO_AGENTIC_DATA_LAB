# L5 · MCP con gobernanza BAGO

`GovernedMCPAdapter` trata `tools/list` como descubrimiento no confiable:

```text
MCP discovery
  → capability descriptor
  → explicit BAGO registry
  → effect classification
  → ExecutionRequest
  → Permit
  → MCP transport call
  → MCPCallReceipt
```

Descubrir una tool no la registra ni le concede autoridad. El registro exige
que BAGO asigne explícitamente un `EffectType`. La política local sólo permite
automáticamente `READ`; `WRITE`, `CREATE`, `DELETE` y otros efectos quedan en
`REQUIRE_HUMAN` hasta que exista aprobación explícita.

El adapter valida el subconjunto de JSON Schema necesario en el borde
(`required`, `properties`, `type`, `enum` y `additionalProperties`), vincula
el `Permit` al `ExecutionRequest` y genera un receipt incluso para denegaciones
o fallos de transporte.

## Demo local

El servidor real de ejemplo está en `scripts/local_mcp_server.py` y utiliza el
SDK MCP instalado. La demo abre una sesión stdio, descubre dos tools, permite
`get_lab_status` como `READ` y bloquea `propose_lab_note` como `WRITE` antes de
enviarlo al servidor:

```powershell
python scripts/run_mcp_demo.py
```

El recibo queda en `evidence/mcp_governed_demo.md`. La evidencia visual se
genera desde esa misma ejecución:

```powershell
python scripts/render_mcp_evidence_video.py
```

Produce `evidence/mcp_governed_demo.mp4` y su hash SHA-256 asociado. El vídeo
es una evidencia de revisión local, no una afirmación de despliegue productivo.
