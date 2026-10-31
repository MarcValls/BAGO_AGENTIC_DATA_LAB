# Cierre de los objetivos más próximos

De los 24 objetivos inicialmente abiertos o parciales, se cierran 9 en su alcance: dos entregas históricas reconciliadas y siete incrementos de interfaz revalidados. Quedan 15 abiertos o parciales.

| Objetivo | Dictamen de alcance |
|---|---|
| github-update-20261022 | Entrega histórica y publicación contrastadas; aceptación independiente recuperable. |
| readme-clarity-20261022 | Entrega histórica y publicación contrastadas; aceptación independiente recuperable. |
| agent-saved-tasks-20261020 | Aceptación acotada; criterios y límites en la matriz independiente. |
| context-viewer-20261020 | Aceptación acotada; criterios y límites en la matriz independiente. |
| eval-equal-height-20261020 | Aceptación acotada; criterios y límites en la matriz independiente. |
| model-assignments-20261020 | Aceptación acotada; criterios y límites en la matriz independiente. |
| model-footer-20261020 | Aceptación acotada; criterios y límites en la matriz independiente. |
| provider-status-line-20261020 | Aceptación acotada; criterios y límites en la matriz independiente. |
| workspace-compact-20261020 | Aceptación acotada; criterios y límites en la matriz independiente. |

Se preservan los fallos anteriores. La regresión final en Docker sobre el commit b1b4d524a0e936300a71da36e0c0276e061fa34e produjo 1792 PASS y 2 SKIP, más 114 subtests. Los skips corresponden a OCR WinRT y CIM de Windows; la suite Windows completa anterior sigue registrada como FAIL.

Se repararon dos defectos reales: una regresión del reloj podía convertir el resultado de una delegación en INCONCLUSIVE al construir su traza; el footer de Modelos podía quedar fuera del área visible y Salir no cerraba Configuración. La segunda reparación superó 21 comprobaciones en la App real con APIs sintéticas, en escritorio y móvil, sin acceder a proveedores ni tomar el foco.

El cierre de Workspace aplica la decisión posterior que centraliza la selección de carpeta en Proyectos y conserva el retorno con foco desde Contexto. No se reinstala el selector anterior.

Square/color sigue parcial: faltan Chat, Capabilities, Builder e Inspector respecto del conjunto originalmente exigido; la matriz describe la cobertura exacta. No se declara cierre global de BAGO5 ni de la misión de continuidad, que continúa NO_GO por sus criterios pendientes.

Las reparaciones quedan en la rama codex/nearest-goals-close-20261031; no se integran en main ni sustituyen los archivos sucios del checkout original.

[Aceptación](ACCEPTANCE.json) · [Revisión independiente](../review/RESULT.json) · [Matriz por objetivo](../review/goal-matrix.json) · [Regresión](../regression/SUMMARY.json) · [Paquete de evidencias](../PUBLICATION_README.md)
