# Goal: ADL-AGENT-RUN-GOVERNED-001

**Estado:** PREPARED / NOT_FROZEN / NO_GO
**Repositorio:** MarcValls/BAGO_AGENTIC_DATA_LAB
**Rama propuesta:** codex/adl-agent-run-governed-f1-20261015 (PR #58 draft).
**Base remota congelada:** main@79149cdbc4174103a351ba454c3e71a50034d056.
**Propósito:** crear la infraestructura de agent.run gobernado por autoridad verificada, autorización exacta, permisos de uso único, gateway/sandbox tipados, receipts durables y verificaciones ADL independientes. No confundir runner de una inferencia con efectos.

## Entregable actual — contrato antes que integración

- `docs/agent-run/contracts/GOVERNED_EXECUTION_V1.md` — 22 reglas normativas y estados.
- `docs/agent-run/contracts/CONFORMANCE_VECTORS_V1.json` — 43 vectores esperados, todos NOT_RUN para integración.
- `docs/agent-run/contracts/FINGERPRINT_GOLDEN_V1.json` — fixture y digest SHA-256 del snapshot completo para comprobar mutación.
- `docs/agent-run/contracts/AS_IS_REUSE_MAP_V1.md` — owner, reutilización, adaptación, brechas y rutas/código actual.
- `change_requests/CR-GEX-001-RECEIPT-SEMANTICS.md` — ambigüedad entre ausencia de receipt y ausencia de efecto, pendiente canon.

## Fases posteriores, sujetas a gates

FREEZE ADL BASELINE → TRACE EXECUTION PATH → AUDIT REQUEST/PERMIT → REVIEW NORMATIVE CONTRACT + VECTORS → RESOLVE CANON CONFLICT → INDEPENDENT CONTRACT RETEST → FREEZE V1 → AUTH + DURABLE PERMIT + STATE MACHINE → ONE TYPED READ FIXTURE → ADL INDEPENDENT VERIFICATION → CAPABILITY PRESERVATION → WINDOWS/NEGATIVE TESTS → CRIT-ADL-GOVERNED-EXECUTION-001.

## Prohibiciones y evidencias

- Sin firma Ed25519 comprobada, autenticación backend y ledger de intentos/recibos, **no iniciar tool effects**.
- Mantener `/ws/agents/run`, `agent.run`, `mcp.execute`, `sandbox.execute` en **UNAVAILABLE / FAIL_CLOSED**.
- No presentar `LocalRestrictedBackend` como aislamiento SO; no activar shell, proceso no confiable ni egress por este contrato.
- No modificar el canon congelado ni `README.md` manualmente; change request formal y generador único.
- PREPARED no es VALIDATED/FROZEN. Test E2E, autenticación real, restart/concurrency, teamctl de esta misión, generador README, Windows retest y CRIT independiente: **NOT_RUN** hasta evidencia específica y fechada.
- Preservar todos los componentes actuales y comparar capacidades/regresiones antes de integrar.

**Cierre prohibido** hasta P0=0/P1=0 con evidencia de la rama/commit exactos, solicitud/permit firmado, gateway real, efecto observado, receipt durable, verificación independiente y fallos.