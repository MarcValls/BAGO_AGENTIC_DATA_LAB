# Browser Bridge v0.1 — integración con conformidad ADL y evidencias

**Estado:** PROPUESTO / PENDIENTE DE IMPLEMENTACIÓN Y VERIFICACIÓN  
**Fecha:** 2026-10-29  
**Plan receptor:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
**Base original del plan:** `ae8e53e14afa763f816eac9e11ddc0e8a24cdc56`  
**Referencia posterior inspeccionada en main:** `1ebf9b1b2c5cd75de8dd34dddb0cc581588327c4` (2026-10-29). Revalidar main antes de implementar.  
**Alcance del cambio:** solo especificación de integración; no código, política activada ni efectos de navegador.

## 1. Decisión que debe preservarse

Las pruebas de Browser Bridge se relacionan con **el contrato de conformidad de dominio que ADL ya tiene**, sin crear otra autoridad, otra puerta de ejecución o un segundo ledger. La conformidad es una evaluación de la candidata y sus evidencias gestionadas, nunca un permiso de ejecución.

Tres límites no negociables:

1. **Chrome concede acceso mediante un gesto real del usuario reconocido por el navegador.** `activeTab` solo está disponible después de invocar la extensión por una vía admitida por Chrome (por ejemplo, acción de barra); un mensaje del chat, una política persistente de ADL, un flag `shared=true` o una simulación de clic no conceden ese permiso. La extensión comprueba el permiso vigente en la operación efectiva. Un cambio de origen o cierre de pestaña lo revoca según el modelo de Chrome; una lectura posterior necesita un nuevo gesto si ya no hay concesión.
2. **ADL decide y registra la ejecución usando GEX, no la conformidad.** La autorización del backend sigue siendo independiente y adicional a la de Chrome. El adaptador, la extensión, Inspect, los tests y el modelo no emiten permisos alternativos. El usuario no se convierte en una capacidad ejecutable por aceptar una conclusión de conformidad.
3. **Sin recibo terminal durable después de `DISPATCH_INTENT` no hay éxito.** El resultado operativo permanece `UNKNOWN / RECONCILIATION_REQUIRED` hasta reconciliación fundamentada con evidencia independiente; ni ACK de transporte, ni respuesta del LLM, ni timeout, ni PASS de conformidad autorizan `SUCCEEDED`. No reintentar ciegamente un despacho ambiguo.

## 2. Lo realmente existente que se debe reutilizar

- `src/contracts/domain_conformance.py` ofrece `verify_domain_manifest` para el contrato `adl.domain_manifest.v1` y `verify_domain_conformance` para un paquete normalizado. Son **funciones de lectura**: no ejecutan checks, no escriben un registro nuevo, no autorizan y no activan dominios.
- `docs/domain-conformance/source/03_DOMAIN_CONFORMANCE_TEST_v1.0.md` define **13 controles obligatorios**: `AUTH-001`, `SCOPE-001`, `SOURCE-001`, `STATE-001`, `OPER-001`, `CAP-001`, `EVID-001`, `MEM-001`, `ROUTE-001`, `REL-001`, `VER-001`, `SEM-001`, `KERNEL-001`. Sin un PASS y evidencia válida para cada uno, la candidata no es CONFORMANT.
- `docs/domain-conformance/source/05_DOMAIN_MANIFEST.schema.json` valida la estructura del manifiesto; la verificación semántica del adaptador exige controles exactos y binding a candidato.
- `docs/domain-conformance/ADL_ADAPTER_v0.1.md` especifica que la relación control→comprobaciones requeridas la suministra **el host confiable**, no el propio paquete evaluado. Los IDs de evidencia son comprobaciones ya declaradas como requeridas en el work item gestionado por `teamctl`, con recibos, handoff y candidato coherentes.
- `tests/contracts/evidence/test_domain_conformance.py` usa comprobaciones sintéticas y demuestra la validez del mecanismo, **no la adecuación semántica de pruebas de Browser Bridge**. El fixture que utiliza una comprobación común `acceptance` para muchos controles no debe convertirse en cobertura sustantiva del dominio navegador.
- `docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md` separa resultado observado, recibo durable y verificación independiente; para un despacho ambiguo prescribe incertidumbre y reconciliación.

**Nota de procedencia:** las fuentes `05_DOMAIN_MANIFEST.schema.json` y `03_DOMAIN_CONFORMANCE_TEST_v1.0.md` fueron reconstruidas y aceptadas para ADL el 2026-10-29; no son copias históricas recuperadas. El estado VERIFIED del adaptador en documentación corresponde a sus pruebas acotadas, no a una integración Browser Bridge.

## 3. Separación de responsabilidades y ciclo

`Usuario → gesto Chrome → concesión temporal activeTab → binding de pestaña → solicitud ADL → GEX valida/autoriza/consume → DISPATCH_INTENT durable → transporte → lectura → recibo durable → verificación independiente → consulta de conformidad de candidata`.

El orden es conceptual: la evaluación de conformidad de una versión de Browser Bridge se realiza en un **gate de entrega/revisión**, fuera del camino de ejecución de cada lectura. Nunca se invoca `verify_domain_manifest` como condición autorizadora del despacho en runtime. El permiso de Chrome debe continuar siendo válido cuando se ejecuta la lectura, además de que GEX haya permitido la operación.

**Propietarios de evidencia:**

- Operación individual: propietario durable existente de GEX para solicitud, permiso, consumo, intención, resultado, recibo y verificación. Reusar su ledger; si la ruta GEX sigue limitada a `fixture.read`, ampliar el registro/capacidad mediante contrato explícito y su propia revisión, **sin rebautizar la fixture ni crear otro almacén autoritativo**.
- Conformidad de candidata: work item/mission, checks requeridos, recibos y handoff gestionados por `teamctl`. Esto es el mecanismo existente de evidencia de entrega, distinto del estado runtime de operaciones; no se incorpora un ledger adicional.
- El adaptador de dominio: **proyección de solo lectura** que devuelve conclusión candidate-bound, `authorization_granted=false`, `activation_performed=false`, `persisted=false`; no cambia ninguno de los propietarios anteriores.

La correlación propuesta utiliza `candidate_sha256` para la candidata y `request_digest`, `attempt_id`, `receipt_id` y `receipt_digest` para cada intento. No son claves de autorización por sí mismas; las referencias cruzadas deben validarse por las autoridades existentes.

## 4. Mapeo propuesto de los 13 controles (no configurado todavía)

Los identificadores de la columna «check propuesto» son **nombres de diseño**, no checks existentes ni ejecutados. Codex deberá acordar, registrar y ejecutar las comprobaciones reales como `required_checks` del work item de `teamctl` antes de construir la política host-owned `required_checks_by_control`. Un check PASS solo sirve cuando sus aserciones son semánticamente suficientes y un verificador independiente las ha comprobado.

| Control vigente | Check propuesto | Aserción específica Browser Bridge | Vectores del plan |
| --- | --- | --- | --- |
| AUTH-001 | `bb_auth_boundary` | Ni página, host, extensión, chat ni conclusión CONFORMANT conceden autoridad; GEX es único decisor. | T02, T05, T08 |
| SCOPE-001 | `bb_scope_tab` | Solo pestaña/origen/proyecto compartidos; negativos explícitos y revocación por cambio de contexto. | T02, T03, T04 |
| SOURCE-001 | `bb_source_trust` | Texto web no confiable, procedencia y extracto identificados; no se promueve a instrucción. | T08, T09 |
| STATE-001 | `bb_state_uncertain` | Pérdida de recibo tras despacho termina en UNKNOWN/RECONCILIATION_REQUIRED, nunca SUCCESS. | T10, T11 |
| OPER-001 | `bb_operation_effect` | Lectura tipada y limitada; el despacho se registra antes del efecto; sin navegación/escritura. | T01, T06 |
| CAP-001 | `bb_capability_real_chrome` | Una operación real Chrome demuestra concesión por gesto humano y lectura con alcance fijado. | T01, T02, T13 |
| EVID-001 | `bb_evidence_linkage` | Evidencia candidate-bound y cadena request/attempt/receipt/verification; sin recibo no se inventa PASS. | T10, T11 |
| MEM-001 | `bb_no_memory_grant` | Sesiones o bindings recordados no restituyen `activeTab` ni permisos revocados. | T03, T04 |
| ROUTE-001 | `bb_routing_single_gateway` | Chat y control manual convergen en GEX; vía directa UI→host y mensajes falsos se rechazan. | T08, T12 |
| REL-001 | `bb_relation_versions` | Dependencias explícitas entre GEX, extensión, host, protocolo y manifiesto; sin targets ambiguos. | T05, T13 |
| VER-001 | `bb_version_compatibility` | Candidata/contratos/versión de host y extensión coinciden; incompatibilidades se bloquean. | T05, T07 |
| SEM-001 | `bb_interface_semantics` | APIs de compartir, leer, revocar, consultar estado e Inspect tipadas y documentadas. | T01, T11, T12 |
| KERNEL-001 | `bb_no_kernel_collision` | Sin ledger paralelo, permiso alternativo, ejecución a través de conformidad ni apertura general del sandbox. | T02, T06, T10 |

Esta matriz conserva **los 13 IDs obligatorios exactos**. No añade un 14.º control ni modifica el schema. Los tests específicos se asignan como evidencia de los controles existentes. El host de conformidad fija el mapping y `teamctl` conserva handoffs; el productor de Browser Bridge no decide qué pruebas son obligatorias.

**Distinción fundamental:** un test que provoca una pérdida de recibo y confirma que el runtime deja la operación en UNKNOWN puede dar PASS como *prueba correcta del manejo de incertidumbre*. Ello **no** convierte la lectura ambigua en SUCCEEDED ni VERIFIED_SUCCESS.

## 5. Vectores de aceptación que cierran las brechas

- **BB-C01 Gesto auténtico:** con Chrome real y extensión MV3, una persona invoca la acción y comparte una pestaña elegible; una lectura gobernada posterior puede ejecutarse. Registrar versión, origen/ID de pestaña, actor, permiso temporal y resultado, sin capturar secretos. El harness automatizado no sustituye por sí solo esa observación.
- **BB-C02 Sin gesto:** un mensaje de chat, un comando del host, un registro persistido, un evento sintético o un reload no conceden `activeTab`; denegar la lectura si falta permiso.
- **BB-C03 Doble autoridad:** con concesión Chrome vigente pero permiso ADL denegado, no se lee; con permiso ADL pero sin concesión Chrome, tampoco.
- **BB-C04 Revocación y contexto:** navegación a otro origen, cierre, cambio proyecto/perfil y reinicio de Chrome invalidan bindings/aprobaciones según su contrato; no reinterpretar una concesión antigua como nueva.
- **BB-C05 Receipt loss:** provocar interrupción **después de `DISPATCH_INTENT`** pero antes de recibir/persistir recibo terminal. Esperado: `UNKNOWN / RECONCILIATION_REQUIRED`, sin transición a éxito, sin replay automático, con IDs que permiten reconciliación.
- **BB-C06 Conformidad no autoriza:** obtener un resultado `CONFORMANT` para una candidata sintética no habilita feature flag, permisos, host o ejecución; un test que intenta convertirlo en Permit debe fallar.
- **BB-C07 Mapping no autopropuesto:** eliminar un control, inventar evidencia, mapearlo a un check no requerido o usar un handoff de otra candidata impide CONFORMANT.
- **BB-C08 Regresión y evidencia:** conservar tests de `fixture.read`, contratos GEX, `teamctl`, Chat/Inspect, permisos de archivos y README generados; exigir revalidación de la candidata real. No atribuir resultados antiguos a nuevas ramas.

## 6. Orden de implementación revisado

**P0:** inventario actualizado de `main` (incluido PR #101 y cambios posteriores), identidad SHA, propietario real del ledger GEX, cobertura del adaptador de dominio, baselines y áreas activas de Codex.

**P1a:** decidir y revisar asignación semántica de los 13 controles → pruebas y checks host-owned requeridos → contrato versionado de evidencia y binding a candidato. Distinguir pruebas sintéticas, Chrome real y evidencia runtime.

**P1b:** aprobar contrato de permiso Chrome por gesto real, binding de pestaña, doble autorización, `DISPATCH_INTENT` y tratamiento `UNKNOWN`. Delimitar fallos que puedan reconciliarse y qué observación independiente los cierra.

**P2–P3:** transporte host y extensión aislados; no registrar una lectura simulada como verificación Chrome.

**P4:** integración en la autoridad GEX existente, sin nuevo ledger ni permiso derivado de la conformidad. La operación no transita a SUCCEEDED sin recibo durable, conforme al contrato GEX.

**P5–P6:** UI y verificación real Windows/Chrome, checks requeridos de teamctl y evaluación de conformidad read-only candidate-bound, posteriormente a las pruebas; ningún resultado del adaptador activa por sí solo la capacidad.

## 7. Cierre y estado

**PROPUESTO:** mapeo semántico, pruebas BB-C01…BB-C08 y secuencia P1a/P1b.  
**IMPLEMENTADO EN ESTA ENTREGA:** solo este documento de diseño y enlaces desde el plan/handoff.  
**NO COMPROBADO:** existencia de cada check propuesto en teamctl, suficiencia de la política host-owned para Chrome, integración real y persistencia de efectos del runtime.  
**NOT_RUN:** Chrome real, host, Windows, pruebas de integración, suite nueva, verificador independiente y activación.

No promover Browser Bridge a IMPLEMENTADO/VERIFICADO ni cerrar la PR por la publicación de este documento. Antes de iniciar trabajo de código, releer `origin/main`, comparar con la base original del plan y reservar ámbitos; se detectó divergencia entre el plan inicial y el main de 2026-10-29.

**Fuentes primarias:**  
- Chrome `activeTab`: https://developer.chrome.com/docs/extensions/develop/concepts/activeTab  
- Chrome Native Messaging: https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging
