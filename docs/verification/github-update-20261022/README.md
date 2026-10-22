# Actualización de fuentes ADL — 22 de octubre de 2026

## Verificación local de la entrega

Windows, Python 3.14 y Node 24. Entradas reales desde frontend:

| Entrada | Resultado |
|---|---|
| npm test -- --maxWorkers=2 | 14 archivos, 127 PASS |
| npm run test:ui | 8 archivos, 49 PASS |
| npm run test:contracts | 3 módulos TypeScript, 13 PASS |
| npm run build | PASS |
| Generador README con suite completa | 536 PASS, 1 SKIP, 0 fallos |
| Generador README --check --skip-tests | PASS de render; tests NOT_RUN en este comando |
| Contrato normativo y referencia JCS | PASS |

No se suman ejecuciones repetidas como pruebas independientes. El XML conserva el SKIP.
Python 3.11 recibió comprobación sintáctica; este informe no atribuye ejecución local a ese intérprete.
El entorno local usa cryptography 50.0.2 frente a 48.0.0 declarado; la CI instala las dependencias
declaradas en un entorno nuevo y debe pasar antes de actualizar main. No se cambió la dependencia
declarada para ajustarla al equipo. El inventario de versiones figura en environment-dependencies.json.
Los proveedores reales, navegador, Docker y otros sistemas requieren sus propias evidencias.

## Correcciones revisadas y aplicadas

Se preserva el trabajo previo de proveedores, tareas, conocimiento, GEX y frontend.
Tres pruebas frontend se repararon tras revisión independiente: espera de carga de modelo,
uso del runner Vitest y navegación del chat acorde a la interfaz actual.
Una propuesta posterior falló en revisión al asignar pruebas node:test a Vitest; no se aplicó.

La sucesora fija Vitest al árbol tests TSX y ofrece entradas Node separadas para UI y contratos.
Al ejecutar contratos hasta entonces omitidos aparecieron cuatro expectativas obsoletas:
action y trace se migraron siguiendo contratos, adapters y pruebas canónicas actuales.
Los adapters y la fuente de UI no se cambiaron para satisfacer esas pruebas.
Se mantienen ausencia de identidad, éxito sin recibo como unverified, identidad de recibos,
errores, redacción y separación request_id/tool_call_id. La CI incorpora test:contracts.

El [informe diferencial](runner-repair.md) y la [revisión independiente](independent-review.md)
describen fallo anterior, autoridad utilizada, cambio y comprobación posterior.
El [manifiesto aplicado](applied-runner-manifest.json) identifica los seis archivos y copias previas.
Las copias privadas que provocaron descubrimiento recursivo siguen conservadas localmente;
Windows denegó archivarlas. La configuración evita incluirlas como pruebas del producto.

## Integridad y conservación

La [reparación P1](../teamctl-integrity-20261022/README.md) conserva su identidad Windows
0f74f0d818f422d2a9506957e6396070300bbb77d88c602605b4fa647e7cc774.
Se revalidaron todos los archivos de su manifiesto y las ocho fixtures protegidas.
Se excluyen de la publicación configuraciones locales, misión histórica, dependencias,
copias de trabajo, transcripciones y compilados; permanecen en el equipo.

[Puertas finales](final-gates.json), [checks frontend](frontend-checks.json),
[JUnit](backend-junit.xml) y [SHA-256](SHA256SUMS.json) conservan las evidencias de esta ejecución.
Las rutas locales de los recibos identifican su origen; las copias enlazadas permiten consultar los resultados.
La evidencia Windows no acredita bytes de otro checkout ni anticipa el resultado de GitHub Actions.
