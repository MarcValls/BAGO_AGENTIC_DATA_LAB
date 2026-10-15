# CR-GEX-001 — Baseline, reconciliación de contratos y brechas

**Repositorio:** MarcValls/BAGO_AGENTIC_DATA_LAB
**Base fijada antes del cambio:** main @ bdf2be825cfd16b3a9b9435efcb7c2384309cf25.
**Rama candidata:** codex/cr-gex-001-contract-v1-20261015.
**Naturaleza:** inspección estática de archivos GitHub; no se ejecutó el código de producción ni se comprobó un worktree del host Windows.
**Objetivo limitado:** especificar contrato de identidad, solicitud, aprobación, permiso, consumo y evidencia antes de conectar /ws/agents/run.

## Correspondencia con implementaciones reales

| Fuente observada en el commit base | Reutilización o brecha | Decisión |
|---|---|---|
| AGENTS.md, .bago/INDEX.md, .bago/canon/{LAB_CONTRACT,ARCHITECTURE,STATE,ROADMAP}.md | BAGO es fuente de autoridad y exige goal, equipo y README generado | No alterar canon ni README |
| src/orchestration/state_graph.py — ExecutionRequest | request_id, tool_name, effect_type, parameters, proposed_by, context_revision, timestamp | Reutilizar como propuesta legacy; adaptador a solicitud GEX v1; prohibido usar su to_hash() de 16 hex para permisos |
| src/orchestration/state_graph.py — Permit | request_id, decision, constraints, issue/expiry, signed_by | Mantener legacy; GEX requiere firma verificable, principal, workspace, digest completo y consumo durable |
| src/orchestration/governed_execution.py | _fingerprint usa params/workspace; interrupt/resume; checkpoint InMemorySaver; ruta write/pytest en grafo local | No confundir demo L1 con autorización de producción; no promover por mera integración |
| src/context/workspace_binding.py | WorkspaceBinding con repo/branch/commit/context revision/fingerprint | Reusar como atestación de workspace; no autentica usuario |
| src/execution/gateway.py | Ejecuta solo con SandboxRequest tipado y request_id coincidente | Reusar; autorización durable ha de validarse ANTES de llamar al gateway |
| src/sandbox/manager.py | SandboxPolicy deriva perfil/alcance desde Permit; _used_permits es set en memoria | Reusar boundary, sustituir control anti-replay por reserva durable en GEX |
| src/sandbox/backend.py | LocalRestrictedBackend impone controles lógicos; subprocess.run shell=False para ProcessRequest | No es contenedor ni firewall; la seguridad de proceso arbitrario no queda acreditada |
| src/sandbox/specification.py | Capability/Profile/NetworkMode y límites tipados | Reusar vocabulario; perfil no garantiza por sí solo enforcement SO |
| src/sandbox/receipt.py | SandboxReceipt incluye request_id, permit_id, status, error, hashes y refs | Proyectar al ledger sin modificar el recibo legacy; evidencia durable nueva |
| src/adapters/mcp_adapter.py | MCP registry, schema/effect, pre-transport DENY existentes | Reusar adapter para futuro; egress y registro integrado en GEX todavía no demostrados |
| src/api/server.py | /ws/agents/run envía execution_unavailable y cierra 1008 tras Origin-check | Preservar literalmente hasta gate de disponibilidad |
| docs/decision-inspector/contracts/action/decision-action-v1.md | Projection read-only de estado, acción y recibos, distingue unverified | Consumir ledger por adapter de lectura sin promover autoridad |

## Diagrama de secuencia normativo (futuro)

~~~mermaid
sequenceDiagram
  actor U as Usuario
  participant API as API / Principal resolver
  participant P as LLM planificador
  participant R as Capability registry
  participant A as Policy + Approval
  participant DB as Durable store + ledger
  participant Q as Queue
  participant W as Worker
  participant X as ExecutionGateway / MCP adapter

  U->>API: agent.run (cuando se habilite)
  API->>API: autenticar; cargar agente; resolver workspace
  alt identidad o workspace NO verificables
    API->>DB: IngressDenialReceiptV1 + evento de ingreso
    API-->>U: DENIED sin request_id ni proposal_id
  else identidad/workspace verificados
    API->>P: tarea sin permisos de tool
  P-->>API: ToolProposal (sin ejecución)
  API->>DB: ToolProposalEnvelopeV1 + proposal_digest
  API->>R: lookup capability versionada + esquema
  R-->>API: descriptor explícito / unavailable
  API->>API: validar registro, disponibilidad y argumentos contra esquema
  break Registro no resuelto, capability no disponible o esquema inválido
    API->>DB: ProposalDenialReceiptV1 + evento DENIED (proposal_digest)
    API-->>U: denegación; sin permiso ni ejecución
  end
  API->>DB: GEXRequestV1 validado + request_digest + PROPOSED
  API->>A: evaluar principal/agente/workspace/tool/args/efecto
  A->>DB: POLICY_DECIDED (incl. deny)
  opt REQUIRE_HUMAN
    A->>U: mostrar operación completa y request_digest
    U->>A: autenticación + aprobar/rechazar
    A->>DB: APPROVED / REJECTED, firma vinculada
  end
  A->>DB: emitir PermitV1 condicionado
  DB->>Q: job_id (sin autoridad embebida)
  Q->>W: job_id
  W->>DB: CAS permit ISSUED + append DISPATCH_INTENT (atomic)
  DB-->>W: committed / replay denial
  opt Reserva exitosa
    W->>X: operación tipada, scope y límites verificados
    X-->>W: efecto observado / fallo / incierto
    W->>DB: receipt persistido y transición de estado
  end
  DB-->>API: estado persistido y refs de evidencia
  API-->>U: evento WS (no autoridad de ejecución)
  end
~~~

## Hallazgos por severidad (P0/P1/P2)

- **P0-01:** ExecutionRequest.to_hash() excluye parameters, proposed_by, context_revision, timestamp, principal y workspace, y trunca digest; no válido para vincular aprobación GEX.
- **P0-02:** Permit legacy tiene signed_by declarativo, sin prueba criptográfica obligatoria de issuer/principal, y ausencia de aprobación autenticada en el recorrido API.
- **P1-01:** Replay protection del SandboxManager es set + Lock en memoria por proceso; no durable entre reinicios ni workers.
- **P1-02:** Huella de governed_execution.py es mejor que to_hash, pero no incluye principal, versión de registry, policy revision ni autorización externa del usuario; demo L1 ≠ GEX.
- **P1-03:** LocalRestrictedBackend no garantiza aislamiento de proceso/red a nivel OS.
- **P1-04:** No hay evidencia en este estudio de ledger transaccional que registre permisos consumidos, intentos y reconciliación desde el endpoint de agente.
- **P1-05:** WebSocket aplica Origin allowlist; esto no autentica programas locales ni identidades productivas.
- **P2-01:** Decision Inspector es un contrato de lectura; sin adapter GEX se mostrarán unknown/unverified en vez de inferir éxitos.

Los hallazgos son brechas entre contratos actuales y nuevo objetivo, **no se clasifican como regresiones de la ruta L1 validada localmente**.

## Gates, dependencias y preservación

1. **Contrato:** revisar consistencia CR-GEX-001, resolver CR-GEX-002…005, implementar oracle de canonicalización interoperable y probar vectores positivos/negativos por un revisor independiente. Solo entonces FREEZE v1.
2. **Mínimo vertical seguro:** identidad y workspace realmente autenticados, registry local read-only, aprobación/política según efecto, PermitV1 firmado, store/ledger y CAS persistente, paso tipado por gateway + sandbox, recibo durable, fallos y replay. Para cualquier garantía no cubierta, UNAVAILABLE.
3. **Integración:** mantener la ruta existente /ws/agents/run inalterada hasta un E2E real desde API con ausencia de simulación, que pruebe límites, recuperación, fallos y evidencia.
4. **Regresión:** verificar demos L1, MCP, sandbox, trazas, chats, UI y README generator; prueba de comportamiento, no solo presencia de archivos. Capacidad nueva no puede quitar capacidad anterior sin cambio explícito.
5. **Distribuido:** cola/worker/egress fuerte independiente únicamente tras reproducir semantic CAS, idempotencia y reconciliación bajo más de un proceso.

## Verificación disponible en este candidato

- Lectura estática de fuentes y canon por GitHub: REALIZADA.
- 40 vectores de conformidad propuestos con EXPECTED (no ejecutados): SPEC_ONLY.
- Suite pytest, tests positivos y negativos contra ejecutor integrado: NOT_RUN.
- teamctl verify/pair/mission terminal gate: NOT_RUN (no existe checkout del repositorio en este entorno y no se pueden reproducir sus comandos mediante el conector).
- README generación y check: NOT_RUN (no cerrar goal).
- Windows E2E, multi-worker y sandbox OS: NOT_RUN.
- Revisión independiente de contrato: PENDING.

**Dictamen de este documento:** PREPARED / NO_GO para conectar herramientas al endpoint. La publicación del contrato no implica que las brechas estén corregidas en runtime.
