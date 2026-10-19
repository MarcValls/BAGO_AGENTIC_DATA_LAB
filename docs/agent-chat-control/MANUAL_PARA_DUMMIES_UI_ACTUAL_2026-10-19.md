# Manual visual de BAGO

Guía breve para orientarse en la interfaz actual. La conversación es el punto de entrada: puedes pedir lo que necesitas en el chat; si una petición requiere otra vista, BAGO pregunta antes de cambiar de pantalla.

## Qué muestran las capturas

Estas imágenes se tomaron el 19 de octubre de 2026 con Playwright sobre la UI local actual. Las respuestas de API fueron sustituidas por datos de demostración en el navegador: la carpeta `C:/proyecto-demo`, el job, el agente y los resultados son ficticios. No se leyeron archivos reales, no se guardó ningún agente, no se llamó a un proveedor y no se ejecutó ningún trabajo.

## Empezar por el chat

![Chat del orquestador](assets/manual-ui-actual-2026-10-19/01-chat.png)

Escribe una petición con tus propias palabras. Por ejemplo: «muéstrame el historial de jobs» o «quiero crear un agente que clasifique pedidos». BAGO puede presentar el resultado dentro de la conversación. Si hace falta abrir una zona completa de la aplicación, te preguntará antes.

![El historial de jobs aparece dentro del chat](assets/manual-ui-actual-2026-10-19/16-chat-job-history-inline.png)

![Borrador editable del agente dentro del chat](assets/manual-ui-actual-2026-10-19/17-chat-agent-draft-inline.png)

![Confirmación antes de cambiar de pantalla](assets/manual-ui-actual-2026-10-19/18-chat-confirm-screen-change.png)

## Elegir el workspace

![Workspace y capas de contexto](assets/manual-ui-actual-2026-10-19/02-workspace.png)

En **Workspace** puedes escribir una ruta de proyecto o pulsar **Browse…** para elegir una carpeta con el explorador. **Use folder** confirma la selección. Debajo se muestran las capas que delimitan el contexto: memoria general, contexto del proyecto, carpeta de trabajo y memoria de la conversación. La selección de una carpeta por sí sola no autoriza la lectura de sus archivos.

## Zonas de trabajo

![Catálogo de capacidades](assets/manual-ui-actual-2026-10-19/03-capabilities.png)

**Capabilities** muestra las capacidades disponibles y las propuestas que pueden revisarse.

![Formulario de Agent Builder](assets/manual-ui-actual-2026-10-19/04-agent-builder.png)

**Agent Builder** abre el formulario para configurar nombre, descripción, tipo, instrucciones y herramientas. Revisa la vista previa antes de guardar. La captura no guarda el borrador.

![Agent Runs](assets/manual-ui-actual-2026-10-19/05-agent-runs.png)

**Agent Runs** reúne el estado de los agentes y sus ejecuciones. La búsqueda de código duplicado se solicita desde el chat; no es un formulario permanente de esta pantalla.

![Laboratorio de evaluación](assets/manual-ui-actual-2026-10-19/06-evaluation-lab.png)

**Agent Evaluation Lab** sirve para preparar suites y revisar qué se enviaría al proveedor antes de ejecutar una evaluación.

## Consultar resultados con Inspect

Pulsa **Inspect** para abrir el panel de datos. El panel se cierra con la **×** de la esquina superior derecha.

![Decision Inspector](assets/manual-ui-actual-2026-10-19/07-decision-inspector.png)

![Historial de jobs](assets/manual-ui-actual-2026-10-19/08-job-history.png)

![Resumen](assets/manual-ui-actual-2026-10-19/09-summary.png)

![Retrieval y ontología](assets/manual-ui-actual-2026-10-19/10-retrieval-ontology.png)

![Autorización](assets/manual-ui-actual-2026-10-19/11-authorization.png)

![Traza](assets/manual-ui-actual-2026-10-19/12-trace.png)

![Evaluación](assets/manual-ui-actual-2026-10-19/13-evaluation.png)

Estas vistas ayudan a revisar decisiones, trabajos, resúmenes, fuentes recuperadas, autorizaciones, trazas y evaluaciones. En el uso normal, el contenido depende de los datos disponibles para la conversación o el job seleccionado.

## Ajustes

![Proveedores y modelos](assets/manual-ui-actual-2026-10-19/14-provider-models.png)

En **Settings → Provider & models** se revisa el proveedor y el modelo configurados. No compartas claves de API.

![Cognición y contexto](assets/manual-ui-actual-2026-10-19/15-cognition-context.png)

En **Settings → Cognition & context** se selecciona el modo de razonamiento y se consultan las ubicaciones de contexto.

## Abrir este Markdown como PDF

Desde la raíz del repositorio, con Pandoc instalado, puedes generar el PDF con:

```powershell
pandoc docs/agent-chat-control/MANUAL_PARA_DUMMIES_UI_ACTUAL_2026-10-19.md `
  --resource-path=docs/agent-chat-control `
  -o docs/agent-chat-control/MANUAL_PARA_DUMMIES_UI_ACTUAL_2026-10-19.pdf
```

El archivo PDF resultante queda junto a este Markdown. Las capturas deben permanecer en `assets/manual-ui-actual-2026-10-19` para que el conversor encuentre las imágenes.
