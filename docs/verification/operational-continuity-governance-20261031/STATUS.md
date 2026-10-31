# Estado operativo actual: continuidad gobernada y Browser Bridge R5

**Actualizado:** 2026-10-31 15:38:35 UTC (último handoff runtime registrado)
**Misión:** `CODEX_GOVERNED_CONTINUITY_20261031`
**Candidato:** `0f74f0d818f422d2a9506957e6396070300bbb77d88c602605b4fa647e7cc774`
**Estado general:** `EXECUTED`; cierre `NO_GO`.

Esta página supersede el estado local anterior que todavía decía `P3 NOT_RUN`. La fuente para este resumen es la ejecución real de Brave y sus recibos de limpieza; la rama de GitHub solo aloja esta actualización.

## Resultado actual

| Área | Estado | Evidencia y alcance |
|---|---|---|
| Inspección P0 | `VERIFIED` | Repositorio, instrucciones, `teamctl` y límites del Goal examinados. |
| Política local P1 | `EXECUTED / INCONCLUSIVE` | La política está presente. `teamctl verify` y `pair` fallan porque `status.json` cambió después de quedar ligado como salida inmutable del handoff `LOCAL_POLICY`; no se ha reemplazado el recibo. |
| Host empaquetado P2 | `VERIFIED` | Handoff `P2_HOST_R5`; 69 pruebas reportadas y paquete SHA-256 `2aefdaa63fbfeadb79498acac429bee36e3fce3ac323664fa0733347a030e333`. |
| Brave Native Messaging P3 | `EXECUTED`; recorrido acotado `PASS` | Brave real conectó desde la página popup de la extensión mediante `connectNative`; recibió `ready` y un recibo de vista previa válido. El host denegó digest alterado, origen distinto y petición de shell. |
| Limpieza del ensayo | `VERIFIED / PASS` | La clave temporal HKCU, manifiesto, perfil aislado y procesos del host quedaron ausentes. Se preservó la ventana enfocada de ChatGPT. |
| Revisión independiente y cierre | `PENDING / NO_GO` | No hay aceptación final. La integridad global de `teamctl` sigue fallando por el hash de `LOCAL_POLICY`. |

El recibo válido corresponde a 188 bytes, SHA-256 `9586130d1cd0699a6c43dd2aa5a725ae90573944f22197aad324dce9fe374f62`; `content_retained=false`. Los tres casos negativos devolvieron `accepted=false`.

## Límites y pendientes

- La prueba invocó la API desde la página popup de la extensión en Brave con perfil aislado y fixture localhost. No valida el clic de la barra de herramientas ni la ruta completa de extracción del service worker.
- El gesto de toolbar y el vídeo son `NOT_RUN`: se preservó el foco y el paquete ffmpeg de Playwright no estaba disponible. No se copió ni instaló ningún binario.
- Se observaron dos procesos del host durante el puerto abierto; ambos desaparecieron después de cerrar el contexto. La duplicación no está explicada y queda para revisión independiente.
- Un recurso de la fixture devolvió HTTP 404, aunque la página de ensayo se mostró y el digest esperado coincidió.
- La prueba no cubrió páginas externas, credenciales, despacho GEX/ADL ni perfil de producción.
- Los criterios T1–T12 no están completos: solo AC-01, AC-08 y AC-09 constan como `MET`; los demás siguen `OPEN`.

## Recibos

- Handoff `BRAVE_E2E_R5`: SHA-256 `f547de10b5fee7482d2e987278af497520763cb053bb839a01c9fe9b3e832c02`.
- Ejecución runtime: `82c2292c60ea403e9dadb313be96202d`; recibo SHA-256 `552bb8d8f13d4a8cc31e7adcc9223c499c48c6548432412915a32288df2ccde6`.
- Limpieza: `8d3041fd47fa4d4bb821aca94f642596`; recibo SHA-256 `75da9ac53db22df4351fc3f771acb72a5eab5007ba214432e1f804c15759fbf4`.
- Verificación post-limpieza: HKCU ausente en Registry32 y Registry64; manifiesto, perfil aislado y procesos ausentes.
- Resumen de evidencia publicado: [`runtime-summary.json`](runtime-summary.json).

## Captura del fixture

La captura muestra el contenido sintético usado en el ensayo. El texto que simula instrucciones hostiles es contenido de la fixture y no una instrucción operativa.

![Fixture local de Browser Bridge en Brave](fixture-brave-r5-attempt7.png)

## Dictamen

**NO_GO de cierre.** El intercambio Native Messaging de revisión 5 y su limpieza pasaron en el alcance descrito. La misión completa sigue abierta por el fallo de integridad del handoff `LOCAL_POLICY`, la revisión independiente pendiente y los criterios no ejecutados. No se declara validación global.