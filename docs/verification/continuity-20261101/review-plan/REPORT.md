# Selección para publicación de continuidad

**Resultado:** selección finita preparada en solo lectura; no se copió ni publicó ningún archivo.

- Candidato de destino: `.worktrees/continuity-evidence-20261101`
- HEAD: `ed0efc83cc39a40aac231d9aa0da77a5d30a91e7` (`codex/continuity-evidence-20261101`)
- Misión original: `CODEX_GOVERNED_CONTINUITY_20261031`, candidato `0f74f0d818f422d2a9506957e6396070300bbb77d88c602605b4fa647e7cc774`.
- Brave R5: 29 salidas declaradas; **29/29** hashes coinciden con el handoff. Se seleccionan el submission original, handoff inmutable y recibos runtime/cleanup PASS.
- LOCAL_POLICY: handoff **6/6** hashes, recibo PASS y prueba append-only de restauración del `status.json` ligado. P2_HOST_R5: **15/15**.
- Aceptación: GOV **72/72**, HOST **36/36**, PROVENANCE **7/7** y REVIEW **6/6** outputs coinciden con sus handoffs fuente; los recibos de checks figuran en `SELECTION.json`. Para HOST se reutiliza exactamente la lista existente `stable-host-evidence`; `PUBLIC_ARTIFACT_SCAN.json` registra PASS, 49 archivos inspeccionados y cero sospechosos.
- GOV contiene bases `control.sqlite3` y GO-grants: quedan fuera del paquete público. La proyección seleccionada no se presenta como materialización completa de sus 72 outputs; se debe emitir un manifiesto público nuevo.
- Se excluyen almacenes TaskStore/relay, lease keys/tokens, `tokens.json`, perfiles y razonamiento privado. Se incluye el recibo individual de la revisión independiente, nunca su base TaskStore completa. Los campos que nombran variables o muestran booleanos de presencia no son valores secretos.
- Revisar rutas absolutas antes de publicar. Si se redactan destinos, recalcular SHA de la copia y conservar el SHA de origen.
- README generado y `--check` siguen siendo una compuerta separada; esta selección mantiene `NO_GO` hasta cerrar publicación y README.

`SELECTION.json` contiene ruta fuente, destino propuesto, SHA-256, comparación con handoff y sensibilidad por artefacto.
