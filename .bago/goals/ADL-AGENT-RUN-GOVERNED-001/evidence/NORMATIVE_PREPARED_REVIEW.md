# ADL-GEX-V1 — evidencia de preparación del contrato

**Tipo:** baseline/revisión estática; **NO** es validación de ejecución gobernada.
**Fecha:** 2026-10-15.
**Repositorio:** MarcValls/BAGO_AGENTIC_DATA_LAB.
**Base inspeccionada:** main@79149cdbc4174103a351ba454c3e71a50034d056.
**Candidato con contrato/vectores revisado:** 43e809ccb1b189d2e12f1165bd83b8b8aba1b278.
**PR:** #58 (borrador). El commit que añade este informe será posterior; revalidar SHA del HEAD antes de cerrar.

## Comprobaciones con evidencia

| Afirmación | Procedimiento | Resultado | Límite |
|---|---|---|---|
| Baseline y HEAD fijados | GitHub REST ref main y branch | 79149cd... base y 43e809c... candidato revisado | no es `git status` de worktree local |
| Reglas y vectores | GitHub connector fetch_file + inspección JS de doc/JSON | PASS: 22 IDs normativos únicos; 43 vectores únicos; cobertura 22/22 | comprobación estructural; NO prueba de comportamiento |
| Estados de vectores | inspección de CONFORMANCE_VECTORS_V1.json | PASS: 43/43 implementation_status=NOT_RUN | no existe runner probado para estos casos |
| Hash de fixture | Python local, ASCII JSON sorting equivalente al subconjunto JCS de fixture | PASS: e651dafc... (base) y eaca9cf8... (fixture-beta) difieren | no equivale a conformidad JCS completa ni Ed25519 |
| Preservación estática | GitHub compare main...branch | PASS: 7 archivos añadidos, exclusivamente docs/agent-run y .bago/goals; código runtime, catálogo y README sin modificaciones | no evalúa aplicación viva |
| Endpoint controlado | src/api/server.py:2083-2102 + test_agent_execution_unavailable.py | Sigue `execution_unavailable` por fuente existente | no ejecutado con la propuesta normativa |

## Defectos y gates abiertos

**P0 OPEN:** autenticación principal/backend; FullRequestEnvelope integrado; emisor/validador Ed25519; permit revocación durable; claim/attempt/dispatch ledger; receipts persistidos antes de declarar resultado; reconciliación; evaluador independiente.

**P1 OPEN:** aislamiento real de SO y network egress; path TOCTOU; control de secretos; tests Windows; preservación diferencial en UI para futuros cambios.

**Conflicto canónico OPEN:** CR-GEX-001 (sin receipt => no claim de éxito, no ausencia factual de efecto), canon NO editado.

**NOT_RUN:** teamctl de esta misión y handoff formal, suite local en worktree, generador README, `--check --skip-tests`, pruebas vivas de permisos, MCP, sandbox, Windows y CRIT independiente.

## Evidencia CI del candidato previo

En PR #58, para commit 8b0ad0df9c1301bacd9051db6627c20d6889f47b:
- CI run 38710059839 FAIL (248 tests PASS, posterior paso README check FAIL).
- README consistency run 38710059815 FAIL por README generado desactualizado.
Un PASS de pruebas no implica PASS global. Comprobar runs vinculados al commit del contrato antes de cualquier decisión.

## Dictamen

**APTO COMO CONTRATO CANDIDATO / NO_GO PARA FREEZE / NO_GO PARA EJECUCIÓN.**

Siguiente acción: resolver CR-GEX-001 sin saltar el canon, coordinar misión en worktree aislado conforme AGENTS.md, auditar consistencia del contrato y los vectores, retest independiente, luego FREEZE y solo después integrar la primera lectura tipada. Ninguna capacidad se promueve por este cambio documental.