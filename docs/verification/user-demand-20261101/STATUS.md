# Recorrido real y reparación de tareas de BAGO5

Estado del candidato: GO_SCOPED local de las dos reparaciones; comprobación LIVE, revisión de fuente independiente y controles de README completados. El resultado de publicación y CI se registra separadamente en el PR de esta rama; este documento acredita el cierre local previo a publicar. Base obtenida de `origin/main`: `ed0efc83cc39a40aac231d9aa0da77a5d30a91e7`.

Se añadió una vista de lectura Tabla para CSV/TSV en el editor existente. Texto conserva la edición; abrir o cambiar de vista no guarda el archivo. La respuesta del agente aparece separada de la solicitud enviada. Editar tarea manualmente recarga la tarea guardada, enfoca el editor y exige confirmar el descarte de un borrador. Copiar como borrador conserva la procedencia y exige guardar antes de ejecutar.

Revisar por agente independiente utiliza otro perfil guardado y requiere confirmación explícita. El backend vuelve a comprobar los hashes del run y del perfil antes de llamar al proveedor; guarda un snapshot, solicitud, respuesta o error y correlaciones. El historial original permanece intacto. La revisión recibe únicamente texto, sin herramientas ni permisos heredados.

**Límite P3 documentado:** se verifica separación de perfiles, no independencia de modelo, proveedor o persona. En el ensayo real ambos usaron Codex `gpt-6.1-sol`. La UI muestra el modelo del revisor y advierte que su respuesta no acredita ejecución, verificación ni aceptación del trabajo original. No se impone otro proveedor como requisito que el usuario no haya solicitado.

- Pruebas del implementador: 36 backend y 137 frontend PASS; TypeScript/Vite PASS. El transporte del modelo fue sintético en esas pruebas.
- Revisión de fuente por otro agente: 14 backend y 29 frontend PASS, 17 comparaciones de hashes correctas; sin defectos P1/P2 encontrados en ese alcance. La precisión P3 anterior permanece explícita.
- Comprobación LIVE por root, separada del implementador: 18 criterios PASS en Brave existente y proveedor real. Los cuatro POST negativos fueron rechazados sin añadir revisiones. Los recibos `csv-visual` y `review-visual` están exportados por bytes.
- Revisión real `taskreview_e3118e712c08474f8faf9920bf14b116` sobre `taskrun_8f7aaadbce8a4e4892e95b009cb7fc53`; SHA fuente `7c6db027daa384a643a8375624b45271617b2963ae0cfa6fbe13f43b143ea12e`. Señaló los casos exactos ausentes y afirmaciones sobre permisos sin evidencia visible.

[Vídeo de 38:01](BAGO5_usuario_real.mp4), silencioso con texto explicativo. [Timeline Markdown](TIMELINE.md), [CSV](TIMELINE.csv), [JSON](TIMELINE.json), [subtítulos opcionales](SUBTITULOS.srt), [manual para usuarios](MANUAL_USUARIO.md), [flujos pendientes](FLUJOS_PENDIENTES.md). El resultado global del recorrido fue 16 PASS, 5 FAIL y 4 BLOCKED; PASS sólo acredita el criterio concreto de cada flujo. El vídeo contiene cambios de versión, un corte de captura y repeticiones identificadas; no representa una única ejecución continua de una versión congelada.

El SHA-256 del vídeo final es `7aac98961fda90ac45fc89266c55a89f85be675a9670c573bba377f5ab0708d2`. Se normalizó a 1920×1170 para reproducción compatible. La captura A, B, el intento gris inicial y los eventos originales se conservaron localmente en el archivo histórico; no se eliminó ningún original.

`PUBLICATION_INDEX.json` relaciona 274 archivos lógicos con sus objetos crudos inmutables. Ejecutar `python verify_publication.py` desde esta carpeta permite comprobar sus hashes sin Windows, credenciales o acceso al runtime. Esa comprobación no vuelve a ejecutar el modelo ni valida el producto. No se exportaron las bases de datos/configuración del runtime ni secretos.

Continúan abiertos los fallos del panel inicial, menú colapsado, lectura del CSV desde chat y las rutas de ejecución de código y multitarea indicadas en el timeline. Esta reparación no declara solucionada toda la aplicación. No se ha autorizado una integración en `main`.

## Acceso a Jaeger observado

La investigación posterior del acceso a Jaeger se conserva en `JAEGER_ACCESS_DIAGNOSIS.json`. Las seis referencias del chat en este runtime son `local_only` y no contienen URL Jaeger. El chat conserva Detalles de traza por respuesta y sólo muestra el enlace si el backend aporta una exportación confirmada. Las rutas actuales de Tareas y revisión textual no incorporan metadatos de Jaeger: esa integración sigue pendiente. El acceso por respuesta facilita la investigación individual; una vista de conversación aporta la secuencia conjunta y no sustituye la correlación individual. Esta investigación es posterior al vídeo de 38:01 y no se presenta como una nueva prueba grabada de Jaeger.

## Controles de cierre locales

El generador real `python scripts/generate_dynamic_readme.py` ejecutó la suite completa: 1.806 PASS, 2 SKIP y 0 FAIL/ERROR (114 subtests adicionales). `--check --skip-tests` pasó en Docker y en el worktree final de Windows. Los dos CLOSE tienen recibos y handoffs; teamctl informa ADMINISTRATIVE_DONE, que por sí mismo no implica validación del producto. La aceptación acotada usa además las observaciones LIVE y la revisión separada de fuente.

La imagen Docker exacta fue `sha256:3d92378210d9a4b5411f2f74f9bfe08bd1f90787c5426b589e8b95486c243480`: contenía pypdf 6.21.2 mientras el candidato fija 6.21.4. Esa ejecución acredita ese entorno, no el pin exacto de CI. Las dos omisiones son WinRT real y CIM de Windows en Linux. Los nuevos documentos públicos se añadieron después de capturar la entrada Docker; el check final del worktree sí los incluyó.
