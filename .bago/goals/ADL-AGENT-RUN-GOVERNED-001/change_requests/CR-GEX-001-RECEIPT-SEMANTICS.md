# CR-GEX-001 — Receipt no implica ausencia material de efecto

**Estado:** PROPOSED / NOT_APPROVED.
**Objetivo:** ADL-AGENT-RUN-GOVERNED-001.
**Base:** main@79149cdbc4174103a351ba454c3e71a50034d056.
**Autoridad afectada:** .bago/canon/ARCHITECTURE.md, Invariante 2 y ADR-003.
**Fingerprint antiguo:** debe fijarse a SHA-256 completo del documento fuente durante el proceso teamctl antes de aprobación (NOT_RUN).
**Fingerprint propuesto:** debe calcularse del candidato textual aprobado, todavía no fijado (NOT_RUN).

## Texto existente y conflicto

El canon indica «Sin receipt = no ocurrió (para propósitos de auditoría)» y «Lo que no tiene receipt no existe para propósitos de auditoría». Es coherente como restricción de *claims*, pero es materialmente peligroso interpretarlo como «el efecto no sucedió». En sistemas con fallos entre ejecución de un efecto y persistencia de receipt hay resultados indeterminados.

## Cambio mínimo propuesto, no aplicado

Aclarar las frases sin borrar su propósito: «Sin evidencia verificable, ningún efecto puede declararse realizado con éxito ante auditoría. La ausencia de receipt NO demuestra que no ocurrió un efecto. Si existe posibilidad de efecto sin confirmación persistida, la ejecución queda RECONCILIATION_REQUIRED; no se repite automáticamente ni se promociona a SUCCESS».

Además, distinguir ExecutorReceipt (declaración del ejecutor) y ADLVerificationResult (prueba independiente) para autorizar claims de VERIFIED_SUCCESS.

## Impacto y validación

Consumidores: estado de agent.run, Permit/ExecutionGateway/SandboxManager, LocalTrace, Decision Inspector, conformance tests y evaluaciones ADL. Los artefactos históricos conservan su scope y no se reetiquetan sin revisión. Requiere decisión explícita de gobernanza, change request oficial teamctl, fingerprints old/new, invalidaciones documentadas y tests GEX-V025/V026/V035.

**NO ACTION:** la PR de contrato NO modifica el canon. La solicitud queda pendiente de revisión independiente y de materialización mediante teamctl en un worktree aislado.