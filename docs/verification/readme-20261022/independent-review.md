# V01 — revisión independiente final del README

**PASS, P0=0/P1=0 dentro del alcance finito.** Recibo Suite
`bf13eb1825b34f8892067f1977185a1b`, exit0. README revisado SHA-256
`0731c7d5a88f5528861c923ed6b947c0eb8a931a2c2572e0fdc814418d131bf1`.
Esta entrega permite la puerta I01; no declara regresión completa, integración,
publicación ni cierre. El revisor escribió los tests T01 pero no las fuentes
generator/manifest/documentación/README del constructor B01.

## Identidad y controles realizados

Se revalidaron todos los outputs SHA de los handoffs B01 y T01 antes de
consumirlos, los tres targets finales B01 contra sus copias y los dos tests T01
contra el worktree. Sus manifiestos/README/registro/CI-summary/tests tienen hashes
idénticos antes/después de V01. No se editaron fuentes o pruebas tras T01.

| Criterio | Evidencia ejecutada/observada | Conclusión |
|---|---|---|
| Orden lector | Ocho headings exactos: propósito→frontend→tests→demo→arquitectura→historia→documentación→contrato | Información actual antes del detalle histórico |
| Primera lectura acotada | 108 líneas fuera de details;525totales;7bloques equilibrados | Bajo límites autorizados180/600 sin borrar historia |
| Evidencia actual separada | Snapshot b0/run39813814372, datos Windowsf2 y CI viejo38665463586 conservados con sus alcances | No se atribuye resultado viejo a una candidata nueva |
| Cifras exactas | Hashes de metadata.stdout/log.stdout coinciden con ci-summary; extractos limpios se reconstruyen de raw | Backend539, Vitest14/127, UI49, contratos13 y buildPASS pertenecen a CIb0 |
| Identidad CI | Metadata completed/success, headSha b0 y URL coinciden con registro; pasos pertinentes completed/success | Run39813814372 y candidata exacta respaldados |
| Merge versus ejecución | git rev-parse de ambos árboles coincide b0/f253 | Igualdad de árboles, no ejecución separada de CI para el merge |
| Cinco negativas | Candidata/evidencia ausentes, COLLECTED, schema ajeno, pathescape | Todos producen ValueError; no se promueven a PASS |
| Colección distinta de PASS | Render0 igual a render987654321; sentinela ausente | Contador de colección no altera las cifras publicadas |
| Entrada CLI efectiva | python scripts/generate_dynamic_readme.py --check --skip-tests, proceso nuevo, exit0 | «README verificado; suite NOT_RUN (550 casos recogidos)»; no ejecución completa |
| Enlaces nuevos | Diferencia de links respecto al README base f253;15locales nuevos resueltos dentro del worktree | Cero enlaces locales nuevos rotos |
| Preservación | Run/SHA histórico, fases, Bruma, Jaeger, skills y límites siguen presentes | Reordenación y plegado conservan evidencia |

Las instrucciones de arranque/build/proveedores describen archivos y comandos;
V01 no arrancó API, navegador, proveedor ni frontend. Disponibilidad de motores
o modelos no se infiere de la capa visual. El script de lanzamiento y npm siguen
siendo fuentes enlazadas, no resultados ejecutados por esta revisión.

## Resultados previos y alcance

T01 ejecutó17pruebas focales contra las fuentes finales selladas, exit0,
recibo `09bf27edc5b044b8993459a9a0d46e75`, sin drift. V01 consumió esa evidencia
revalidada y reconstruyó controles/CLI actuales; no repitió ni ejecutó la suite
completa. La orden CLI de V01 recogió550casos y lo declaró NOT_RUN, no550PASS.

Dos arranques iniciales del harness V01 se conservan como FAIL operativo:
`f788d2509d5e4223b20189f418186aaf` comparó texto raw coloreado con resumen limpio;
`7a1c68e32ea848069a04348b92106586` retiró ANSI real pero no la forma literal `^[`
presente en gh-log. Se corrigió solo esa normalización no semántica, manteniendo
primero la comprobación de SHA de los bytes raw. No se cambió producto, registro,
resultado CI ni criterios; no constituyen defectos de la candidata. Las dos
versiones del harness están preservadas. La ejecución final es la única usada
para la puerta review.

`manifest.json` detalla los hashes, handoffs consumidos, cinco rechazos, enlaces,
argv/código y fingerprints de logs. `result.json` SHA-256:
`5c30d7a04fbc627a4f6d402f06c8a889b52eea1325ff4ec3926c341899308d92`.
I01 del coordinador debe ejecutar la regresión completa y ambas órdenes README
sobre el estado final, inspeccionar diff y encargarse de cualquier publicación.
