# C01 — revisión independiente de candidata ADL

Candidata revisada: `0f74f0d818f422d2a9506957e6396070300bbb77d88c602605b4fa647e7cc774`.
Dictamen independiente: **PASS en candidata aislada**, P0=0 y P1=0 dentro del
alcance de AUTH-001/B04-AUTH-002. Trece grupos reconstruidos y cinco casos propios
pasaron; 211 invocaciones registradas CLI/fixture contando las lecturas inicial/final
de identidad. Recibo Suite `fa9684b54d2d480397564ba9bd0e1f1a`, exit0. Comprobación
documental gestionada `7b4c359bfe304399a7954cc5cc259cec`, exit0. Hash de
`result.json`: `56deb77832386c368dfb7eca45a0a5443c21941edb581401a23e9cbe737cac29`.
El dictamen ejecutado y su alcance están en `result.json`; los resultados de cada
proceso se conservan en `reconstructed-regression.json` e `independent-cases.json`.
Este informe no declara integración en el checkout activo ni cierre del goal.

## Independencia e identidad

El revisor no implementó B01 ni modificó la candidata. Antes de consumir su
harness/evidencia revalidó los 51 outputs del handoff persistido B01; todos
coincidieron. `consumed-B01.json` fija los hashes. Se leyó controlador, helper,
esquemas de entrega/misión/work item, protocolo, comunicación, wrapper y contratos
publicados. La reconstrucción usa procesos CLI nuevos y raíces sintéticas nuevas;
no copia el PASS del implementador. Se añadieron cinco casos propios.

`review-manifest.json` liga antes/después de todos los archivos de candidata y
entradas; también revalida los outputs B01 al terminar. Identidad ejecutable ADL
finita de 13 archivos, manifiesto completo de entrega por separado. La identidad
Suite `f5ab9b9a…` de los recibos de coordinación es distinta y no sustituye a la
identidad ADL anterior.

Entorno observado: `.venv/Scripts/python.exe`, CPython 3.14.5, importación real de
`jsonschema==4.23.0` mediante overlay absoluto `output/teamctl-p1-deps-20261022`.
`environment.json` conserva ejecutable, versión y archivo importado. Bootstrap
local dentro del comando evita depender del PYTHONPATH exterior eliminado por
Suite. No se instaló ni modificó el entorno, no se llamó a proveedor/servicio.

## Criterios → ejecución observable → conclusión

Los nombres siguientes identifican casos en los dos JSON de ejecución. Sus
`calls` contienen argv, stdout, stderr y código de salida por proceso. Una
variante negativa solo pasa al observar rechazo no cero y ausencia de aceptación.

| Criterio obligatorio | Caso ejecutado / observable | Conclusión si PASS registrado |
|---|---|---|
| Entrega válida se acepta y consume | `valid_accepted_consumed_wrapper_restart`: run-check real, handoff P, verify nuevo proceso, claim C mediante wrapper, handoff C | Recorrido efectivo canónico y wrapper acepta y consume evidencia válida |
| Salida inexistente se rechaza | `schema_scope_identity_receipt_negatives`, variante `missing_output` | Sin transición DONE ni handoff persistido |
| Salida modificada o eliminada invalida | `modified_output_blocks_consumer_and_recovers`, `deleted_output_blocks_consumer_and_recovers` | verify/inspect/ready/pair/continue/claim rechazan; restaurar bytes exactos permite recuperación |
| Hash incorrecto se rechaza | Negativas `wrong_hash`, `uppercase_hash`, `null_hash`, `output_missing_digest` | Digest suministrado no se corrige silenciosamente |
| Rutas fuera del alcance se rechazan | `outside_scope`, `changed_outside_scope`, traversal/absolute/UNC/backslash/ADS/device/dot/emptysegment y junction Windows | Confinamiento, contrato de rutas y scopes observados desde CLI |
| PASS sin campos obligatorios se rechaza | `missing_*` y `verification_missing_*`, tipos/extra fields, JSON duplicado | Esquema completo se aplica antes de aceptación; campos no inventados |
| Otra misión o candidata se rechaza | `other_mission`, `other_candidate`, `other_scope`, `foreign_receipt_rejected` | Identidades de entrega/recibo no intercambiables |
| NOT_RUN no satisface ejecución obligatoria | `not_run`; propio `independent_required_check_contract` | Entrega rechazada y misión REPAIR sin required_checks no se inicializa |
| Texto de comando sin recibo no acredita ejecución | `typed_without_receipt`, `typed_wrong_command`, `wrong_check_id`; propio `independent_latest_execution_supersedes_PASS` | Exige recibo gestionado del comando/check real; PASS viejo rechazado tras nueva ejecución FAIL |
| Consumidor bloqueado si invalida dependencia | `claimed_consumer_rechecks_dependency`: C ya CLAIMED, mutate P, run-check/handoff C rechazados | Se revalida antes de ejecutar y aceptar consumidor existente |
| Reinicio revalida integridad | Todas las llamadas CLI son procesos nuevos; stale cases verifican después de mutate/delete | No se confía en DONE conservado en memoria |

Pruebas adicionales de recibos: `receipt_log_mutation_blocks_and_recovers`,
`receipt_mutation_blocks_and_recovers` y
`independent_all_receipt_outputs_rechecked`. Este último declara dos outputs en
el recibo, incluye solo uno en el handoff y elimina el otro tras aceptación:
verify y claim del consumidor deben rechazarlo. Omitirlo del handoff no elimina
la obligación de revalidar el observable registrado en el recibo.

## Relación archivo / recibo y límites

El código aplica existencia/hash/scope a cada output del handoff y revalida todos
los outputs/logs del recibo consumido. El recibo prueba que un argv concreto se
ejecutó con su código, identidad y observables declarados. No afirma que ese
comando creó todos los archivos del handoff: un test puede revisar código creado
antes. `independent_output_receipt_relationship_boundary` comprueba precisamente
ese límite y que alterar después el archivo del handoff bloquea al consumidor.
La calidad semántica de un comando arbitrario requiere su propia aceptación;
el planificador no convierte un comando trivial en prueba funcional de producto.
No se considera P1 la ausencia de esa garantía ajena al contrato solicitado.

La integridad local cubre cambios detectables frente a hashes registrados, no
autenticación del host contra quien puede reescribir todo el almacén. Tampoco es
un sandbox OS, ni elimina carreras entre comprobar y usar archivos. No se afirma
cancelación de descendientes ni reversión de efectos al fallar persistencia.

## Compatibilidad y CR-P1-001

`legacy_passive_read_current_gate_rejection` y el caso propio
`independent_exact_historical_snapshot_no_rewrite` reconstruyen legado mínimo y
copia exacta de los 55 archivos observados. status/inspect leen las cuatro tareas
históricas sin añadir candidate/scope/recibos; evidencia etiquetada
LEGACY_UNVERIFIED. verify/ready/pair/claim/close rechazan y los hashes antes/después
son idénticos, sin lock nuevo ni migración. El monitor/API continúa siendo una
proyección pasiva de mission/work_status, no una puerta ni prueba de agentes vivos.
El test HTTP y la regresión completa quedan al coordinador tras integración.

`published_contracts_default_mission` compara bytes kit/plugin de protocolo,
misión y plantilla; inicializa misión predeterminada moderna y valida esquema.
El positivo utiliza el wrapper `runpy` hacia el controlador canónico: no se añade
otro coordinador. La plantilla es sintáctica y no demuestra ejecución.

`CR-review.json`, producido por `check_cr.py`, comprueba explícitamente:

- SHA de CR `b2afe68d4708c3917c7635606ac652646e4d5386bb1e28f55911619ec29723e4`.
- Handoff original predecesor conservado `3dda13728bb902660bbecfa59d65b3dd9c002839d2043d25498e9043d19e7d4d`.
- Solo cambian los dos TEAM_PROTOCOL; los restantes bytes de ambas candidatas
  son iguales. Protocolos pasan de SHA `47357af6612560d4796c735ccbec377cb8cb973111770069d6977b1e981a2f89`
  a `26508c678346577b26b0e98d5019c0fd096bde350189f99f2a016878759ba022`.
- Cabecera v0.3 y regla de cierre distinguen AUDIT con PRODUCT abierto de REPAIR,
  que bloquea P0/P1 aplicable; ADMINISTRATIVE_DONE no valida un producto.
- CR declara consumers_started=false. Esta revisión reconstruye evidencia nueva
  para la identidad sucesora; no refirma evidencia previa como aceptación nueva.

## Intentos, restricciones y disposición

Primer intento C01 `8a5ff07ae57b44c29e615c4e42edf8b4`: FAIL por timeout exterior
predeterminado de 60s; no proporciona dictamen. Segundo intento
`eaf5369985684023b04a80f03199c2f9`: FAIL por ruta de recibo temporal que excedía el
límite Win32 en fixtures demasiado profundas. El controlador devolvió error y
conservó la puerta cerrada. Resultados íntegros conservados en `attempt-2/` y los
recibos de ambos intentos. El tercer intento usa raíces nuevas cortas bajo
`fixtures/verification/a/{r,i}` y timeout 600, sin cambiar candidata.

El intento de crear symlink nativo registra WinError1314 cuando Windows niega
privilegio: NOT_RUN, nunca PASS. El rechazo de reparse se ejercita mediante
junction Windows realmente creada. No exige elevar privilegios ni modificar OS.

El dictamen final requiere cero casos fallidos y ausencia de P0/P1 dentro de la
corrección. No autoriza modificar otra misión ni cierra producto activo: integración,
pruebas desde controlador activo, regresión completa, dos órdenes README e inspección
final del diff pertenecen al coordinador y permanecen pendientes en esta entrega.
