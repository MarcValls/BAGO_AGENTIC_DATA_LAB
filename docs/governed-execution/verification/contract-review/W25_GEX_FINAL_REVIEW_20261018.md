# W25: revisión final independiente del contrato GEX y del gate de promoción

**Dictamen:** `FREEZE_ELIGIBLE`  
**Candidato:** `MarcValls/BAGO_AGENTIC_DATA_LAB`, HEAD `599764dbe0e6008f7b2eb9cbedd605c9a711aee9`.  
**Misión vigente:** SHA-256 `56565610dbb07ee5a5e1b596318e6e66a051de38a13805e636847e413577dc3b`.  
**Independencia:** no participé en W23, W24 ni en la reconciliación de misión CR-023.  
**Alcance:** contrato/schema/norma/estado/vectores y elegibilidad del gate. **No se ejecutó runtime**; no se habilitó identidad, firma de producción, ledger, dispatch ni fixture.

## Fingerprints y reconciliación

| Artefacto | SHA-256 actual | Cotejo |
|---|---|---|
| `.bago/canon/ARCHITECTURE.md` | `4a7e700cffac20473822a3803da4fac73b52db2fc92a4044567ba0ddaf56beda` | coincide con CR-017 propuesto |
| `docs/governed-execution/GEX_V1_SCHEMA.json` | `1059ceb9f13fb7452cabe46a4736c886680cd47ab16ce15ec7410ec59e781027` | coincide con CR-022 hash 1 |
| `docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md` | `208702196b234c473678b2041b12b15942a4f774d238f2e42d14b8c6f5dc08a3` | coincide con CR-022 hash 2 |
| `docs/governed-execution/GEX_V1_STATE_MACHINE.json` | `afbd0eef32ab18fdc2cb2999f98c0f683628bbb92ff139a65f2309a0343eb7c1` | coincide con CR-018 estado de máquina |
| `docs/governed-execution/GEX_V1_CONFORMANCE_VECTORS.json` | `b72484c1284d7e9e6edd734320b975e9e55941544768b9e428791ff92727d8f6` | coincide con CR-022 hash 3; conserva perfil read-only de CR-021 |
| `docs/governed-execution/verification/test_gex_contract_consistency.py` | `27e5cd2ab34c29510e6c598aab6bd0ca050574e90510757c5d4221ab849edd34` | coincide con CR-022 hash 4 |
| `.bago/team/kit/missions/agent-decision-inspector.json` | `56565610dbb07ee5a5e1b596318e6e66a051de38a13805e636847e413577dc3b` | coincide con CR-023 misión propuesta |
| `.bago/team/runtime/change_requests/CR-022-GEX-VERIFICATION-BINDING.json` | `1e178c6e245721b1f3941801b1828690ef9bc8ca9529cac5b36b1d242b9ec947` | fingerprints actuales cotejados |
| `.bago/team/runtime/change_requests/CR-023-RECONCILE-GEX-PROMOTION-FINGERPRINTS.json` | `a35e84f7ec54b93bc4ec7f26d2b37325531acd2e6003a62316f48e48f49f4155` | misión propuesta cotejada |

CR-018 conserva como histórico el schema y vector antiguos; el gate W21 declara explícitamente que esos dos fingerprints quedan supersedidos por CR-022, que incorpora la corrección read-only de CR-021. El fingerprint de máquina de estados y el perfil de producción Ed25519 de CR-018 siguen vigentes. W21 compara los cuatro artefactos actuales con los cuatro primeros fingerprints de CR-022, y la misión actual con el fingerprint de CR-023. CR-017 arquitectura y CR-018 estado de máquina coinciden. El caso GEX-037 actual es `UNAVAILABLE / DENY`, cero dispatch y recibo `DENIED`; las pruebas mantienen la prohibición de efectos mutantes en v1.

## Cierre de los hallazgos previos

- **W20-P1-01, éxito verificado sin evidencia:** cerrado. Schema requiere digest SHA-256 de postcondición y al menos una evidencia para `VERIFIED_SUCCESS`; los vectores GEX-VFY-008/009 y las pruebas negativos rechazan digest nulo y evidencia vacía.
- **W20-P1-02, persistencia sin vínculo de resultado:** cerrado. Para `VERIFICATION_RESULT_PERSISTED`, schema exige `verification_result_id`, `request_digest`, `attempt_id` y `boundary_receipt_id` no nulos; vectores GEX-VFY-010/011 y pruebas negativas lo cubren.
- **W20-P1-03, evento/digest ausente de la norma:** cerrado. §5 enumera el evento y define el vínculo/durabilidad; §5 da la fórmula del digest del recibo con dominio, JCS, UTF-8 y SHA-256; §5A da la entrada firmada exacta para ApprovalV1 y PermitV1.
- **W20-P1-04, fingerprint histórico incompatible con el gate:** cerrado por CR-023 y la misión revisada. W21 distingue los campos históricos supersedidos de CR-018, preserva los fingerprints aún vigentes y requiere las huellas actuales de CR-022/023.

**Hallazgos P0 abiertos: 0. Hallazgos P1 abiertos: 0.**

### P2 residual

El fixture Ed25519 conocido usa un mensaje de fixture y no una instancia `PermitV1` completa. La norma sí define exactamente la entrada firmada (`domain separator || JCS(PermitV1 sin signature)`), incluyendo todos los claims, `issuer`, `key_id`, `signature_algorithm` y `contract_version`; el schema fija Ed25519. El criterio de implementación W15 exige comprobar firma sobre claims completos. Mantengo esto como refuerzo de cobertura P2, no como defecto normativo P1.

## Verificaciones ejecutadas sobre el candidato exacto

| Comando/acción | Resultado | Alcance |
|---|---|---|
| `python -m pytest -q -p no:cacheprovider docs/governed-execution/verification/test_gex_contract_consistency.py` | **PASS: 20 passed** | Consistencia estructural, negativos, vectors y checks JCS; no es runtime. |
| `node docs/governed-execution/verification/jcs_reference.mjs docs/governed-execution/GEX_V1_CONFORMANCE_VECTORS.json` | **PASS, exit 0** | Referencia emite los 24 casos finitos de Appendix B y muestras Unicode/UTF-8/orden UTF-16; las pruebas comparan bytes y digests golden. |
| Reproducción adversarial W20 sobre `VerificationResultV1` y `LedgerEventV1` | **PASS** | Exitos válidos aceptados; digest nulo, evidencia vacía, ID resultado nulo y request/attempt/receipt links ausentes rechazados. |
| Cotejo programático CR-017/018/021/022/023 y condiciones W21 | **PASS** | Canon/state machine siguen vigentes; schema/norma/vectores/tests y misión coinciden con CR-022/023; supersesiones expresas. |
| `git diff --check -- <contrato, canon, misión y CR revisados>` | **PASS** | Sin errores de whitespace. |
| `python .bago/team/kit/scripts/teamctl.py verify` | **PASS** | Integridad del protocolo/misión en el estado revisado. |

## Cierre W25

`FREEZE_ELIGIBLE`: no queda P0/P1 abierto en el contrato ni en el gate al fingerprint indicado; todos los checks exactos pasan y W20-P1-01/02/03/04 quedaron cerrados o reconciliados. Esto habilita a W21 para su decisión explícita y separada de promoción, no cambia por sí mismo el estado a producción. La identidad autenticada, firma Ed25519 productiva, ledger durable, ejecución del fixture y verificador runtime permanecen `NOT_RUN` y fuera de esta declaración.
