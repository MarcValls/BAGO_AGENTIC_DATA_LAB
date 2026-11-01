# BAGO5: manual del recorrido grabado

Este manual explica lo que se hizo en la interfaz y cómo reconocer el resultado. Acompaña al [vídeo BAGO5_usuario_real.mp4](BAGO5_usuario_real.mp4), de **38 minutos y 1 segundo**. Es una grabación real del área visible de Brave, **sin audio**, con texto explicativo incorporado. No es una captura de todo el escritorio.

Puedes seguir el recorrido con la [cronología legible](TIMELINE.md), abrirla como [tabla CSV](TIMELINE.csv) o consultar los [datos JSON](TIMELINE.json). También tienes los [subtítulos SRT](SUBTITULOS.srt). El vídeo ya lleva texto aunque no cargues el SRT.

El recorrido contiene **25 flujos: 16 PASS, 5 FAIL y 4 BLOCKED**. PASS significa que se comprobó el resultado concreto indicado; no certifica toda la aplicación. FAIL conserva un resultado contrario al esperado. BLOCKED significa que no se pudo completar el flujo. NOT_RUN identifica algo que no se ejecutó.

## Antes de empezar

Usa una carpeta de pruebas. En esta demostración se utilizó exactamente:

```text
D:\301020256_PRUEBA_BAGO5_ADL
```

Los archivos de ejemplo están dentro de `demo-usuario`. Los vídeos, capturas y verificaciones se guardan en la carpeta de este manual. Elegir un proyecto, conceder acceso a sus archivos y ejecutar una tarea son acciones diferentes: comprueba cada confirmación en pantalla.

Durante el recorrido se cambió el runtime local para mostrar las funciones posteriores de CSV y de tareas. Por eso el vídeo documenta una secuencia con cambios, no una única versión inmutable de BAGO5. No acredita instalación de escritorio, publicación ni integración en `main`.

## 1. Abrir el chat y comprobar el modelo

**Vídeo: 00:00:27–00:02:12, F01–F02.**

1. Abre o recarga BAGO5.
2. Si aparece el panel de Proyecto e Historial sobre el chat, ciérralo manualmente para continuar. En esta prueba volvió a abrirse: el arranque directamente en el chat sigue siendo un fallo abierto.
3. En Configuración, abre el apartado de proveedores y modelos. Comprueba el acceso al proveedor y habilita el modelo que quieras usar.
4. Distingue el modelo configurado del registrado en una ejecución concreta. Se comprobó acceso a `gpt-6-luna`, pero las ejecuciones reales posteriores de este recorrido identifican `gpt-6.1-sol`. No se atribuyen esas respuestas a Luna.

## 2. Pedir un cálculo sencillo en el chat

**Vídeo: 00:02:12–00:03:56, F03–F04.**

1. Formula el cálculo y el texto que necesitas.
2. Mira a qué función te dirige la aplicación antes de confirmar nada. La primera petición sobre una respuesta a un cliente acabó en un borrador de Comunicaciones que exigía un contacto; no calculó el presupuesto y no se envió ningún mensaje.
3. Para reproducir la parte que sí funcionó, pide expresamente calcular y explicar el presupuesto en el chat, sin preparar un envío.
4. Contrasta los números: la reformulación devolvió **222,00 €** de subtotal, **22,20 €** de descuento y **199,80 €** de total, además de una pregunta sobre la entrega.

La reformulación permitió continuar; el desvío de la primera petición sigue registrado como FAIL.

## 3. Seleccionar el proyecto de pruebas

**Vídeo: 00:03:57–00:04:35, F05.**

1. Abre la gestión de proyectos desde la interfaz.
2. Selecciona `D:\301020256_PRUEBA_BAGO5_ADL`.
3. Revisa el proyecto y los archivos mínimos que propone crear. Confirma la operación revisada.
4. Comprueba que la carpeta activa mostrada coincide con la elegida.

La selección real de esa carpeta quedó comprobada. El acceso de lectura y escritura se conserva separado de la selección del proyecto.

## 4. Crear, corregir, mover y recuperar un archivo

**Vídeo: 00:04:36–00:06:48, F06–F09.**

1. En la gestión de archivos, crea la carpeta `demo-usuario` y prepara `pedidos.csv` con los datos de ejemplo.
2. Revisa la creación y confírmala. Abre el archivo para comprobar que contiene el CSV: en el recorrido ocupaba **183 bytes**.
3. Modifica las unidades del pedido de Bruno de **5 a 6**. Revisa la sobrescritura y confirma. Vuelve a leer el archivo; la cabecera y las otras filas deben conservarse.
4. Mueve y renombra el archivo como `demo-usuario/archivo/pedidos-final.csv`. Comprueba que el origen desaparece y el destino conserva su contenido.
5. Envía el archivo de prueba a la papelera. Después, restáuralo desde la papelera y vuelve a abrirlo.

En esta prueba la modificación, el movimiento y la restauración fueron reales. Después del cambio de Bruno, el movimiento y la recuperación conservaron el mismo SHA-256. Una huella SHA-256 sirve para comparar los bytes del archivo; no evalúa si sus datos comerciales son correctos. Los detalles están en [F07](F07-file-check.json), [F08](F08-file-check.json) y [F09](F09-file-check.json).

## 5. Leer un CSV como tabla o como texto

**Vídeo: 00:24:49–00:31:28, R19–R21.** Estos son los ensayos repetidos que sí quedaron recapturados.

1. Abre el CSV guardado desde Archivos.
2. Selecciona **Tabla**. En el ejemplo de pedidos se mostraron **siete columnas y tres filas de datos**.
3. Cambia a **Texto** para consultar el CSV original. Cambiar de vista no debe guardar ni ejecutar nada.
4. Para entender los formatos especiales, observa R20: aparecen una celda con coma, comillas internas, un salto de línea, `<b>texto literal</b>` y `=2+2`. El HTML y la fórmula permanecen como texto; no se ejecutan.
5. Para probar un error sin cambiar el archivo guardado, introduce en el borrador un CSV con comillas sin cerrar. Comprueba que aparece el aviso.
6. Descarta el borrador y vuelve a abrir el archivo guardado. En R21 se recuperó la tabla válida sin cambiar los bytes ni la fecha de modificación.

Ver una tabla en Archivos no equivale a que el chat haya leído o calculado sus datos. Las comprobaciones de estos pasos están en [R19](R19-check.json), [R20](R20-check.json) y [R21](R21-check.json).

## 6. Reconocer el límite de lectura del chat

**Vídeo: 00:06:49–00:12:23, F10–F12.**

1. Si pides al chat analizar un CSV, comprueba si aparece una lectura real y una respuesta basada en ese archivo.
2. En el recorrido, escribir la ruta no fue suficiente: el chat volvió a pedir un archivo autorizado.
3. **Consultar archivo** rechazó CSV con el diagnóstico `path is not an allowed text or Markdown source`.
4. También se guardó acceso READ a `demo-usuario`, pero el chat volvió a pedir el archivo y no produjo la tabla ni los importes solicitados.

Ese análisis quedó sin ejecutar. La vista Tabla posterior resuelve la visualización del CSV, pero no demuestra que se haya resuelto este recorrido de análisis mediante chat.

## 7. Guardar una tarea y entender su respuesta

**Vídeo: 00:12:24–00:19:07, F13–F15.**

1. Crea o selecciona un perfil de agente y guarda su tarea.
2. Revisa el alcance mostrado antes de pulsar **Ejecutar tarea**. Guardar el perfil o asignarle herramientas no demuestra que esta vía pueda utilizarlas.
3. En la tarea guardada de este recorrido se pidió expresamente **sólo un plan** para `calcular_pedidos.py` y su archivo de pruebas, sin escribir ni ejecutar comandos.
4. Ejecuta únicamente si quieres solicitar la respuesta del modelo. Abre después la ejecución del historial y distingue **la solicitud enviada** de **la respuesta recibida**.

La respuesta real fue un plan distinto del texto solicitado: **1.958 caracteres de respuesta frente a 420 de solicitud**. No se crearon los archivos Python ni se ejecutaron pruebas. El plan reconoció que no disponía del encargo guardado para identificar sus **tres casos exactos**; los ejemplos propuestos no cumplen ese requisito pendiente.

F15 conserva un defecto histórico de presentación: la solicitud apareció inicialmente bajo «Respuesta recibida» sin distinguirse bien. La [comprobación posterior F22](F22-check.json) documenta el orden y las etiquetas corregidos, pero pertenece al tramo fuera de captura; no convierte retroactivamente F15 en PASS.

## 8. Editar una tarea manualmente

**Vídeo: 00:33:24–00:34:46, R25.**

1. En Tareas, selecciona el perfil correspondiente.
2. Pulsa **Editar tarea manualmente**. Se carga la tarea guardada en el editor; abrirla no la guarda ni la ejecuta.
3. Cambia el texto. Mientras existe ese borrador sin guardar, **Ejecutar tarea** queda bloqueado.
4. Para abandonar el cambio, pulsa **Descartar borrador y cargar tarea guardada**.
5. Si cancelas la confirmación, el borrador permanece. Si confirmas el descarte, vuelve la tarea guardada original.

En R25 se comprobó que este recorrido no modificó la tarea guardada ni las ejecuciones anteriores. Guardar una modificación es una decisión aparte; no se presenta este ensayo de descarte como una nueva tarea guardada.

## 9. Pedir una revisión a otro perfil

**Vídeo: 00:31:46–00:32:42 y 00:34:46–00:36:21, R24 y R26.**

1. Crea o configura un segundo perfil distinto del autor. En el ejemplo, «Revisor independiente de resultados» se guardó con Codex, `gpt-6.1-sol` y cero herramientas.
2. Abre en el historial la respuesta que quieres revisar y pulsa **Revisar por agente independiente**.
3. Comprueba el contenido exacto que se enviará y elige un perfil distinto del autor.
4. Marca la confirmación de enviar exclusivamente esa solicitud y su respuesta, sin herramientas ni acciones sobre archivos.
5. Pulsa **Confirmar y solicitar revisión**. Espera a recibir una respuesta real.
6. Cierra y vuelve a abrir la revisión para comprobar que quedó guardada y vinculada a la ejecución original.

La revisión real señaló, entre otros límites, que faltaban los tres casos exactos del encargo y que un plan no acredita archivos creados ni pruebas ejecutadas. La ejecución original permaneció intacta.

**Es asesoramiento textual:** se utilizó otro perfil, pero el mismo proveedor y modelo que el autor. Esto no demuestra independencia de modelo, aceptación automática ni ejecución de la tarea original. La petición real y la respuesta están conservadas en [R26-context-raw.json](R26-context-raw.json); las [18 comprobaciones LIVE](LIVE_ACTIONS_VERIFICATION.json) acreditan este recorrido concreto.

## 10. Copiar una solicitud como borrador

**Vídeo: 00:36:58–00:38:00, R27.**

1. Abre la ejecución histórica que quieres reutilizar.
2. Pulsa **Copiar como borrador**. Se copia su solicitud al borrador de la tarea actual y se conserva la referencia al origen.
3. Revisa el texto. Copiar no crea otra identidad de tarea ni una ejecución nueva; primero debes guardarlo para poder ejecutarlo.
4. Si no quieres usarlo, descarta el borrador con confirmación. Vuelve a comprobar la tarea guardada y la revisión persistida.

Este flujo se ejecutó realmente y no lanzó una nueva tarea al copiar o descartar.

## 11. Inspeccionar resultados y reconocer los pendientes

**Vídeo: 00:19:08–00:22:58, F16–F18.**

- La petición de dos encargos en paralelo no produjo dos resultados ni concurrencia demostrada.
- Inspector mostró registros de la conversación y un evento `assistant.control COMPLETED`. La propia interfaz avisó de que eso no certifica la tarea ni una evaluación PASS.
- Con la barra lateral contraída, pulsar Agentes volvió a expandirla: el desplegable solicitado sigue pendiente.

Consulta [FLUJOS_PENDIENTES.md](FLUJOS_PENDIENTES.md) para saber qué falta y qué tendría que observarse antes de darlo por resuelto.

## Cómo se conserva el corte de grabación

El [corte de captura](CAPTURE_GAP_VERIFIED.json) conserva el error `Not attached to an active page`. El segmento A terminó aproximadamente en **00:24:15** del montaje. Las acciones originales F19–F23 quedaron en el archivo de eventos y capturas, pero no se presentan como si hubieran quedado filmadas en A.

Se inició una captura B y se repitieron los ensayos de CSV con IDs **R19–R21**. Las acciones posteriores de perfiles, edición, revisión y copia aparecen como **R24–R27**. El vídeo une A y B; no afirma una captura ininterrumpida. Los intentos fallidos de automatización se diferencian de los errores de BAGO, y el intento gris de captura de escritorio quedó excluido del vídeo útil.

La [verificación del vídeo](VIDEO_VERIFICATION.json) registra duración, SHA-256, decodificación correcta y ausencia de audio. Este manual no declara publicación del material ni cierre global de BAGO5.
