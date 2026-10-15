# Mapa de correspondencia AS-IS → ADL-GEX-V1

**Estado:** PREPARED, inspección estática de main@79149cdbc4174103a351ba454c3e71a50034d056. Mapa no equivale a prueba funcional.
**Orden de autoridad:** AGENTS.md → .bago/INDEX.md → .bago/canon/* → objetivo → este diseño. La documentación no reemplaza contratos congelados.

| Fuente real | Contrato/capacidad observada | Decisión | Reglas | Brecha/acción |
|---|---|---|---|---|
| src/orchestration/state_graph.py:44-59,61-76 | ExecutionRequest, Permit y enums | ADAPT | GEX-02/03/07 | to_hash usa solo request_id/tool/effect y trunca SHA; signed_by no firma, falta binding completo |
| src/orchestration/governed_execution.py:37-70,160-349 | LangGraph + fingerprint de demo, interrupt/resume, gateway y LocalTrace | REUSE_WITH_GUARDS | GEX-02/06/13/17 | demo sin identidad autenticada ni checkpoint durable; NO abrir WebSocket por su existencia |
| src/execution/gateway.py:12-43 | Barrera única, SandboxRequest obligatorio, request_id asociado | REUSE | GEX-13 | requiere upstream auth/registered tool/version/full hash/scope; no sustituir clase por un runner paralelo |
| src/sandbox/manager.py:32-55,83-160,162-233 | SandboxPolicy, SandboxRequest, deny+receipt | ADAPT | GEX-07/08/09/13 | replay set+Lock en memoria, token no verificado criptográficamente, intersección lógica |
| src/sandbox/backend.py:28-90,102-148,223-337 | Backend protocol y LocalRestrictedBackend | REUSE_BOUNDED | GEX-13/14 | no OS isolation; riesgo proceso, red y pathname TOCTOU; primera slice con fixture no confiable? NO |
| src/sandbox/specification.py:14-200 | capacidades, perfiles, límites y network mode | REUSE_BOUNDED | GEX-04/14/15 | perfil restringe, pero network=deny no asegura capa SO |
| src/sandbox/filesystem.py:20-110 | FilesystemRequest tipado y scope de rutas | REUSE_BOUNDED | GEX-13/14 | path escape lógico; probar symlink/reparse point, check/use race y ACL de recursos |
| src/sandbox/receipt.py:11-105 | SandboxReceipt(request/permit/sandbox/status, hashes stdout) | ADAPT | GEX-16/17 | receipt de resultado no ledger durable, sin run/trace/attempt/signature verifier |
| src/adapters/mcp_adapter.py:109-260,315-515 | discovery, registration, policy, MCPCallReceipt y call | REUSE_WITH_GUARDS | GEX-04/05/15 | registry in-memory y firma/identidad/egress de producto ausentes; no utilizar discovery como autoridad |
| src/capabilities/manager.py:61-146,149-292 | catálogo y CapabilityStore SQLite de propuestas | REUSE_READ_ONLY / ADAPT | GEX-04/09/20 | catálogo no es permiso; proposal DB no es execution/permit/attempt DB; agent.run=sandbox.execute=mcp.execute UNAVAILABLE |
| src/context/workspace_binding.py:102-306 | WorkspaceBinding Git/context/revision, scope de repo | REUSE | GEX-01/02/08 | prueba de contexto, no autenticación/ACL; app resuelve identidad aparte |
| src/agent/governed_knowledge_agent.py:51-187,457-727 | AgentRun/AgentToolProposal/decision receipts, autorización y verificación | ADAPT_VIEW | GEX-11/16/17 | registros útiles para Decision Inspector; no convertir resultado L9 en autoridad de agent.run |
| src/agent_tools/workspace_read.py + src/api/server.py:1199-1275 | tool loop de chat con lecturas autorizadas por turno | KEEP_SEPARATE | GEX-04/13/19 | no es el pipeline de tool effects de agent.run; conservar su capacidad sin reivindicar aislamiento |
| src/api/server.py:422-431,2083-2102 | origen WebSocket restringido y /ws/agents/run fail-closed | PRESERVE | GEX-01/20/21 | Origin ≠ identidad; no conectar nueva acción antes de gates |
| src/jobs/__init__.py:16-69 | JSON JobExecution y consultas | KEEP_FOR_UI, NOT_AUTH_LEDGER | GEX-09/10/16 | sin transacción ni anti-replay duradero entre procesos |
| docs/decision-inspector/contracts/action/decision-action-v1.md | presentación separada capability/eligibility/authorization/availability/execution/receipt | REUSE_PROJECTION | GEX-17/21 | Inspection no debe emitir permits ni inferir success desde receipt |
| .bago/canon/ARCHITECTURE.md:225-265,343-351 | autoridad BAGO / ExecutionGateway, regla receipt, sandbox lógico | CANON_CHANGE_REQUEST | GEX-12/13/17 | "sin receipt=no ocurrió" **solo** puede querer decir "no acreditado", no ausencia de efecto material |

## Distinciones que no se pueden colapsar

1. Registro de catálogo: datos descriptivos, no herramienta READY.
2. Descubrimiento MCP: herramienta visible, no registrada ni autorizada.
3. Propuesta local de chat: lectura explícitamente autorizada, no runner de efectos.
4. Permit heredado: DTO de decisión y constraints, no prueba criptográfica.
5. Sandbox Receipt: afirmación del ejecutor, no prueba independiente de postcondición.
6. LocalTrace y Jaeger: proyección de evidencia, no autorización.
7. Actor `proposed_by`: puede ser agente; el principal aprobado solo proviene de autenticación backend.
8. Demo integrada L1: validada solo en scope local/lógico de demostración, no en `/ws/agents/run` del producto.

## Contratos futuros y dependencias

- M1 FrozenRequestEnvelope v1: convertir el DTO ExecutionRequest existente en entrada a un snapshot verificable sin romper a consumidores actuales. GEX-01/02/03.
- M2 ToolRegistrySnapshot + PolicyDecision: versionar esquema/efecto/adapter y justificar la decisión, sin cambiar estado de catálogo. GEX-04/05.
- M3 HumanDecision + SignedPermit: identidad de aprobador, key_id y Ed25519, binding canónico, ACL revision y revocación; migrar Permit heredado con versión explícita. GEX-06/07/08.
- M4 DurableExecutionLedger: request, proposal, decision, permit, claim, attempt, dispatch intent, executor receipt, ADL verification, uncertain/reconciliation; transacciones y event chain. GEX-09/10/11/12/16.
- M5 TypedReadFixtureAdapter: única operación local de riesgo controlado a través de gateway+manager; postcondición externa. GEX-13/14/17.
- M6 API/proyección: WebSocket transport y Decision Inspector leen ledger, nunca crean permisividad. GEX-20/21.
- M7 Independent CRIT + capability diff: pruebas negativas, reinicio y concurrencia, Windows y README generator. GEX-19/22.

## Diagrama de ownership

API/Auth/Workspace [principal + sesión] → request congelada [immutable snapshot] → Policy/Registry [decisión] → aprobación humana [actor] → Permit Authority [firma] → Ledger DB [claim+intento] → Gateway [tipo local] / MCP Gateway [externo, no habilitado] → ExecutorReceipt [observación reportada] → ADL Verifier [prueba independiente] → Decision Inspector [lectura].

El primer vertical slice elige fixture de lectura preinscrita con contenido sintético: restringir el modelo, no ejecutar código desconocido ni conectar red ni dar acceso libre a repo. En el backend local actual una lectura arbitraria podría exponer secretos; no es equivalente a "safe" solo por ser READ.

## CRIT y dependencias que impiden promoción

- **P0** request legacy fingerprint incompleto; identidad no autenticada; Permit sin firma verificable; replay no duradero; receipt+reconciliación ausentes de runner.
- **P1** aislamiento de proceso/SO ausente, TOCTOU path, MCP egress sin conexión, test suite y verificación independiente de nuevo ciclo pendientes.
- **Conflicto de canon pendiente**: semántica de ausencia de receipt descrita en archivo separado de change request; no reescribir canon silenciosamente.
- **Punto de integración**: `src/api/server.py@/ws/agents/run` permanece FAIL_CLOSED. El código previo en el ZIP F1 no puede publicarse como Secure Execution sin GEX-07/17.

**Verificación pendiente:** comprobar los 43 vectores de CONFORMANCE_VECTORS_V1.json contra ejecución real y postcondiciones; mantener todos en NOT_RUN hasta entonces.