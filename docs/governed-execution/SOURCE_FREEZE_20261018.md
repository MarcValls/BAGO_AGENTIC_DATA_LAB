# Estado del contrato GEX v1

**Estado:** `FREEZE_AUTHORIZED / SPECIFICATION_ONLY`  
**Candidato:** rama `codex/adl-gex-controls-20261018`, HEAD `599764dbe0e6008f7b2eb9cbedd605c9a711aee9`.  
**Misión:** `AGENT_DECISION_INSPECTOR_V1`, SHA-256 `56565610dbb07ee5a5e1b596318e6e66a051de38a13805e636847e413577dc3b`.

## Decisión

W21 autoriza el freeze del contrato GEX v1 para iniciar la implementación acotada de W14-W18. La decisión se apoya en W25 (`FREEZE_ELIGIBLE`, cero P0/P1), la reconciliación de huellas CR-017/018/021/022/023 y las comprobaciones exactas del candidato. Esto no habilita por sí mismo el endpoint `/ws/agents/run` ni declara disponible ejecución en producción.

## Perfil autorizado para implementar

- Única operación candidata: lectura tipada de un fixture sintético e inmutable.
- Shell, red, subprocess, escritura general y rutas arbitrarias: `UNAVAILABLE / FAIL_CLOSED`.
- `/ws/agents/run`, `agent.run`, `sandbox.execute` y `mcp.execute` se mantienen cerrados hasta integración y verificación runtime independiente.
- W15 debe probar Ed25519 sobre todos los claims canónicos de un `PermitV1`; el vector golden actual no firma un permiso completo (P2 de cobertura).

## Verificación del freeze

- `python -m pytest -q -p no:cacheprovider docs/governed-execution/verification/test_gex_contract_consistency.py`: 20 passed.
- `node docs/governed-execution/verification/jcs_reference.mjs docs/governed-execution/GEX_V1_CONFORMANCE_VECTORS.json`: PASS; 24 casos finitos Appendix B y muestras Unicode/JCS.
- W25 reportó schema negativos rechazados, huellas reconciliadas y `FREEZE_ELIGIBLE`.
- `git diff --check`: PASS.
- `python .bago/team/kit/scripts/teamctl.py verify`: PASS.

## Separación de estado

Contrato: `VALIDATED` para freeze/implementación. Runtime de identidad autenticada, firma productiva, ledger durable, ejecución del fixture y verificador independiente: `NOT_RUN`; no se afirma que existan todavía.
