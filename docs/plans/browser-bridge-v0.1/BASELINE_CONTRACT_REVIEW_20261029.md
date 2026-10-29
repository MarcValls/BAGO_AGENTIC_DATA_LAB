# Browser Bridge — revisión de base y contratos vigentes (2026-10-29)

**Estado de la revisión:** INSPECCIÓN ESTÁTICA DE FUENTES · evidencia de repo GitHub, no ejecución de producto.  
**Repositorio:** `MarcValls/BAGO_AGENTIC_DATA_LAB`  
**Base original de la PR #100:** `ae8e53e14afa763f816eac9e11ddc0e8a24cdc56`  
**Nueva base consultada:** `main@1ebf9b1b2c5cd75de8dd34dddb0cc581588327c4`  
**Última punta documental antes de incorporar main:** `3cf79b934e19b08c6e02a5807cc7b761e651cda4`  
**Propósito:** contrastar las dependencias existentes y actualizar la ascendencia de la rama documental sin reescribir su historia ni alterar `main`.

## Divergencia localizada

Desde la base original, `main` avanzó dos commits e incorporó: adaptador de conformidad F-003 y tests, manifiesto/especificación de 13 controles, documentación de estado de F-003, archivos de propuesta README, y cambios de `.bago/state/PROJECT_STATE.json`. La rama de Browser Bridge solo modificaba tres archivos documentales propios en `docs/plans/browser-bridge-v0.1/`. **Comparación por rutas:** ningún archivo editado en común. Esto permite una incorporación no destructiva de main a la rama mediante merge Git de dos padres, en vez de un rebase forzado que cambie la identidad de commits compartidos.

La incorporación de main no equivale a aceptar ni activar el adaptador de Browser Bridge.

## Contratos inspeccionados en la nueva base

| Superficie | Archivo y blob SHA | Dictamen para Browser Bridge |
| --- | --- | --- |
| Conformidad (adaptador) | `src/contracts/domain_conformance.py` — `87e5525f3ae9e1a63d6fd75f3baa622f9520d13a` | **COMPATIBLE EN DISEÑO:** función read-only `verify_domain_manifest`; valida candidata y handoff mediante `teamctl`; devuelve `authorization_granted: false`, `activation_performed: false`, `persisted: false`. No da autoridad de ejecución. |
| Contrato de controles | `docs/domain-conformance/source/03_DOMAIN_CONFORMANCE_TEST_v1.0.md` — `cd42e0bae2aa11a4ce81276411ee227d84419f74` | **COMPATIBLE EN DISEÑO:** exactamente 13 controles; cualquier obligatorio sin PASS/evidencia válida impide CONFORMANT. |
| JSON Schema | `docs/domain-conformance/source/05_DOMAIN_MANIFEST.schema.json` — `d73de88a6f268eef801fd457da03fdd1e22cdc68` | **COMPATIBLE EN DISEÑO:** `adl.domain_manifest.v1` con `candidate_sha256`, controles y referencias; schema no autentica evidencias, requiere validador semántico. |
| Mapping de evidencias | `docs/domain-conformance/ADL_ADAPTER_v0.1.md` — `663151746262107edeb0e135edc9c00932f3540a` | **APLICABLE:** `required_checks_by_control` lo define el host confiable; referencias deben corresponder a comprobaciones requeridas y verificadas en el handoff gestionado por `teamctl`. |
| Pruebas actuales F-003 | `tests/contracts/evidence/test_domain_conformance.py` — `8af79ff613caa051d7af60d893985c196792233e` | **EXISTEN, NO REEJECUTADAS AQUÍ:** utilizan misión y comprobaciones sintéticas; no prueban concesiones `activeTab`, Chrome real ni semántica del puente. |
| GEX normativo | `docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md` — `a0283d22be5f60b00ef5f75207f4f335ed3c0f4c` | **PRESERVAR:** `PREPARED / CONTRACT REVIEW REQUIRED`, no FROZEN; exige `DISPATCH_INTENT` durable y `UNKNOWN / RECONCILIATION_REQUIRED` si falta recibo terminal, sin éxito presunto. |
| Control GEX | `src/execution/gex_control.py` — `a595bdcf7a1695fe748d1db526c81316a14163b6` | **BRECHA ABIERTA:** camino especial `fixture.read` con constraints `network: deny`, adapter/observer específicos y ledger. La presencia de `RECONCILIATION_REQUIRED` no acredita extensibilidad segura a Chrome. |
| Rutas GEX | `src/api/gex_routes.py` — `8a3fc8bdb6719848cb0638b839208dacfc587dce` | **BRECHA ABIERTA:** API para fixture gobernada; no inferir un endpoint de navegador. |
| Permisos de proyecto | `src/api/project_permissions_routes.py` — `49055606512e50d52a93e665bd7dfa6e8cb0bcf4` | **SIN PROMOCIÓN:** `read_directories`/`write_directories` se refieren a archivos y no a permisos de Chrome. |
| Reglas repo | `AGENTS.md` — `3e16214d25a40b8774c0a40427d80641987bf1d1` | **OBLIGATORIO:** base fresca, pruebas, teamctl y generación de README antes de un cierre real. |

## Resolución contractual

**C1 — Conformidad no es puerta:** el mapeo Browser Bridge→13 controles permanece una propuesta `required_checks_by_control` definida por el host. Cada check deberá registrarse como `required_checks` en trabajo gestionado y demostrar su aserción específica. No reutilizar un único fixture `acceptance` como prueba semántica de todos los controles.

**C2 — Dos permisos necesarios:** una persona concede temporalmente la pestaña mediante una acción genuina reconocida por Chrome y ADL/GEX autoriza la solicitud concreta. Ninguno sustituye al otro. La extensión deberá verificar que la concesión efectiva sigue vigente; sin gesto real no hay `activeTab`.

**C3 — Una única autoridad de efectos:** el ledger ya existente de GEX conserva permisos consumidos, `DISPATCH_INTENT`, recibos y reconciliaciones. `teamctl` registra comprobaciones de entrega; conformidad es lectura de evidencias, no segundo ledger ni autorización.

**C4 — Incertidumbre después de despacho:** si se emitió `DISPATCH_INTENT` y falta recibo terminal persistido, la operación queda `UNKNOWN / RECONCILIATION_REQUIRED` hasta reconciliación con evidencia adecuada. Nunca convertirla en `SUCCEEDED` ni `VERIFIED_SUCCESS` por ACK, timeout o respuesta del modelo. Un test de manejo correcto de incertidumbre puede pasar sin que la operación quede exitosa.

**C5 — Frontera de implementación:** no existe demostración en esta revisión de un adapter GEX de navegador con autoridad, concesión real y recibo durable; antes de implementar se requiere diseñar su ampliación tipada sin debilitar `fixture.read`, revalidar las dependencias y acordar los checks de las pruebas BB-C01…BB-C08.

## Alcance de las comprobaciones

**COMPROBADO POR FUENTE:** identidad de rama y archivos; comparación de rutas contra base original; presencia y semántica textual de las firmas/constantes/controladores mencionados.  
**NO COMPROBADO:** suficiencia de aislamiento Windows, garantías runtime con Chrome real, códigos ejecutados en esta candidata, recibos terminales del puente, compatibilidad exacta del host con extension MV3 ni ejecución de checks `teamctl`.  
**NOT_RUN:** pytest, compilación, generador de README, Windows Chrome E2E y prueba independiente de Browser Bridge.  
**PENDIENTE ANTES DE CODIFICAR:** P0 completo; fijar contracts/required checks de P1 y contrastar trabajo simultáneo de Codex.

La actualización de base es una **operación de Git**, no una aprobación de estos controles. Cualquier CI anterior pertenece exclusivamente al SHA al que fue atribuido. No se modifican `main`, runtime, políticas ni logs de ejecución mediante este documento.
