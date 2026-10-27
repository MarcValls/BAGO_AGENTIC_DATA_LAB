# R9 — Operaciones de archivos en la raíz del proyecto

Fecha: 2026-10-27

Repositorio: `MarcValls/BAGO_AGENTIC_DATA_LAB`

Candidato probado: `codex/adl-project-file-operations-20261027`

HEAD durante la prueba: `74bd848f812be4373d8a44627aa3ca3719678da1`

Tipo de entrega: evidencia de verificación sobre el candidato; no se modificó código de producto en R9.

## Alcance

Se levantó el candidato en `127.0.0.1:8100` con el almacén de datos de pruebas `C:\BAGO_TESTS\PROJECT_PERMISSIONS_20261026\source\.bago\data`. El proyecto seleccionado por ADL fue `D:\PRUEBAS_BAGO5_ADL\PRUEBA_01`, con `project_id=workspace_80e67a1c3d824a8da3e639e97586b285`, READ y WRITE persistentes en `.` y revisión `a10f3f8c8170813e9d9c5d615feba4aa3efd50d063e2b25a578c4e539cc5bfc5`.

Un agente de aceptación guardado en el almacén aislado del candidato usó Ollama Cloud `gemma4:31b` y solo las herramientas `filesystem_inventory` y `filesystem_plan`. Las llamadas reales aparecen en las trazas `agent.chat`, junto con el ID del agente, proveedor y modelo. El agente nunca recibió una herramienta de ejecución de cambios.

Todas las operaciones se limitaron a `ADL_FILEOPS_ACCEPTANCE_20261027`, un fixture sintético dentro de la carpeta raíz del proyecto. Cada mutación pasó por propuesta del modelo, revisión del host y confirmación humana. No se usaron shell, comandos de desarrollo ni lecturas externas para ejecutar las operaciones.

## Resultados

| Operación | Propuesta / plan | Recibo | Resultado verificado |
|---|---|---|---|
| Inventario inicial | lectura `service_1dc7c734756043db81154517b043933e` | evidencia SHA-256 `a1254fa94d8c2bee4bfba099c2291114cae2009359a7f51d8bc85d03e63ce3b8` | `ALLOW`; raíz `D:\PRUEBAS_BAGO5_ADL\PRUEBA_01` |
| Editar `source.txt` | `fsproposal_52dfbabdaafa4d2fbbf9995fb81010b5`; plan SHA-256 `b3c68656b4970534b56dd20d1b5c4560db69cdc7fc83cd15aab85a5426d34893` | plan `7c5530cea75a41b38427ffb17ab72c3f`; recibo SHA-256 `fb2522f7334e521f1a77da7ad7f6d4ad36cc65c509e106e7c798b6013c53f659` | `VERIFIED`; readback SHA-256 `5d284d9a8053954718f2cf3ef9c292df06a01a02f0a316b4a92ecca8c3d0951b` |
| Copiar `source.txt` a `copy-candidate-20261027.txt` | `fsproposal_8f06425470264e5f98ab05ecdd1c8505`; plan SHA-256 `18f08c2cbee5521630956a2b3c2f59a9edd6b3cfe2aa02a3572a0506971e9174` | plan `864fd18461c44b608dac491f9513f99b`; recibo SHA-256 `3a9336149974839089ebe1816aba469bcf001f32fa94c0bc45824e5725bcb22f` | `VERIFIED`; copia con el mismo SHA-256 `5d284d9a8053954718f2cf3ef9c292df06a01a02f0a316b4a92ecca8c3d0951b` |
| Renombrar la copia a `renamed-candidate-20261027.txt` | `fsproposal_811ca6e5a20c4f7b8f4fe3d812452135`; plan SHA-256 `f6b7eba6fe396dca76d5f8c4dc3b7b25a0b1c9f585c5d56a853f70d078b3da77` | plan `124704f72dbd402caf8226a1cbb07646`; recibo SHA-256 `97287cc7c2d7624eed419d27abb0b56c37e6b1786e96222bfdaceab6ea82ab33` | `VERIFIED`; destino conserva el mismo SHA-256; origen intermedio retirado |
| Inventario final | lectura `service_11e9ba4966af4dc991721f3720e320d2` | evidencia SHA-256 `fe1b91265532f4711c62a652e8c1d781bab41537e105e67a4bf11e0ecc4fe21d` | `ALLOW`; `source.txt` y el destino renombrado presentes; `copy-candidate-20261027.txt` ausente |

Los cinco turnos de agente persistieron trazas locales; tres trazas de planificación/lectura llevan respectivamente los IDs `trace-6804a02791ad43ba`, `trace-491ffddc5e924ac9`, `trace-887c2fa7694e412c`, `trace-3f08f3039bf04d3c` y `trace-3fe6e8f5803a431b`. Cada evento raíz registra `provider_id=ollama-cloud`, `model_id=gemma4:31b` y el agente de aceptación. Los recibos y sus hashes se encuentran bajo `.bago-filesystem/receipts/` en la raíz del proyecto; los recibos de llamada y artefactos de salida están bajo `.bago/state/agent-tools/` y `.bago/traces/agent-tools/`.

## Colaboración padre-hijo

En el mismo HEAD y proyecto, el chat principal (`ollama-cloud/minimax-m2.7`) delegó el inventario al agente de aceptación (`ollama-cloud/gemma4:31b`). El hijo ejecutó `filesystem_inventory` una vez, obtuvo `ALLOW`, y devolvió los nombres y hashes al padre. La delegación terminó `PASSED`, `tools_executed=true`, `target_written=false`.

- Conversación padre: `conv_e1fba40a8b524f289de1bb4ecc8a12d2`; traza `trace-12bb472ec0a04456`, SHA-256 `6d1c7bf5dd300c99dc74492bc5572fe4a404c0393d28e14bb50c8393de439f4e`.
- Delegación: `delegation_6403a3754d9c4cf88709469ab5c91aab`; recibo `delegation-receipt_e187e80bef5243cdb0ccf525d071b1b3`, SHA-256 `8cf1002093a606c4a038117c74159f3f483b5be48e6c996d6e29bb7add658661`.
- Conversación hija: `conv_563b956c140140cf964b48d5a203ad1c`; traza `trace-334918fc47f94d05`, SHA-256 `ff0ffb98021a6fcfea40a83c19a298399029919ffec7f6ba0424d474f9001773`.
- Recibo de herramienta hija: `service_be3df5e4f8434f1a968622905c0abf0d`, evidencia SHA-256 `d11ea4908f70139bcd2f75fc2a0b9869fcea379bd38f54f9f50a5483f8ed115a`.

## Verificación focalizada

- Backend/permisos/herramientas: 94 tests y 22 subtests PASS; 1 aviso conocido de compatibilidad Pydantic V1 bajo Python 3.14.
- UI de permisos del proyecto: 5 tests PASS.
- UI de navegación del chat con permiso del proyecto: 1 test PASS.
- Integración focalizada para política de proyecto, review/execute y delegación: 3 tests PASS.
- GitHub CI y consistencia README del HEAD `74bd848f812be4373d8a44627aa3ca3719678da1`: runs `40479074488` y `40479074818` PASS.

## Límites

- `business_acceptance=NOT_RUN`: la integridad y la lectura posterior se verificaron, pero no se evaluó el significado funcional del contenido.
- La colaboración padre-hijo fue de solo lectura; el ciclo de mutaciones fue ejecutado por el agente hijo en turnos directos, con revisión y aprobación separadas.
- El candidato no se instaló ni se fusionó en la instancia abierta de BAGO. El servidor aislado de prueba se detuvo después de capturar los resultados.
- No se probó eliminación permanente de archivos.
- La suite completa y el build local no se ejecutaron como parte de estas comprobaciones focalizadas; CI exact-head está registrado arriba.

Dictamen de R9: **VERIFIED para lectura, edición, copia y renombrado gobernados en la raíz del proyecto seleccionado, con permiso persistente.** La integración en la instancia instalada y la aceptación funcional del contenido permanecen pendientes.

## Comprobación posterior en el BAGO activo: raíz de proyecto y tool call colaborativa

Observación del 27/10/2026 en el servidor activo `127.0.0.1:8098` (PID `92532`; la revisión exacta del código que sirve este proceso no quedó enlazada). La API informó el proyecto `workspace_80e67a1c3d824a8da3e639e97586b285`, raíz `D:\PRUEBAS_BAGO5_ADL\PRUEBA_01`, y política persistente READ/WRITE `.` con revisión `a10f3f8c8170813e9d9c5d615feba4aa3efd50d063e2b25a578c4e539cc5bfc5`, coincidentes con el alcance de R9.

En una conversación nueva del mismo proyecto, el chat principal llamó al proveedor real `ollama-cloud/minimax-m2.7` y delegó una tarea de solo lectura al agente guardado `Candidate project fileops verifier`, proveedor `ollama-cloud`, modelo `gemma4:31b`. La llamada hija ejecutó `filesystem_inventory` dentro de `ADL_FILEOPS_ACCEPTANCE_20261027`; el host registró `ALLOW`, `VERIFIED`, `target_written=false` y el path de la raíz del proyecto. El inventario volvió a observar `source.txt` y el fixture sintético. Referencias exactas, hashes y el alcance no vinculado al commit se encuentran en `live_project_root_collaboration.json`.

La delegación colaborativa de lectura queda **VERIFIED en el runtime observado**. La delegación de un `filesystem_plan` de copia desde el chat principal quedó **NOT_VERIFIED**: dos llamadas reales de `ollama-cloud/minimax-m2.7` contestaron que no encontraban un agente con alcance claro y no generaron propuesta ni operación de archivos. El flujo R9 de edición, copia y renombrado sí está probado en turnos directos del agente con revisión y ejecución host; no se afirma aquí que esas mutaciones fueran realizadas por un agente hijo delegado.

El proceso activo se mantuvo intacto. No se modificaron archivos del fixture durante esta comprobación de colaboración.
