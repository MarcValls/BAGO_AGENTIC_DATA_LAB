# Interacción de mínima fricción

Decisión explícita del usuario, 2026-11-01. Ámbito: BAGO5_ADL y sus worktrees; validación sólo de escritorio conforme a DESKTOP_FIRST.md.

- Una sola aceptación del plan, con alcance visible, inicia la ejecución autorizada. La elección de modelo o agente, preparación y revisión avanzan automáticamente; editar el agente es opcional. No exigir casilla más botón para la misma aceptación.
- Mantener las elecciones de conversación entre mensajes dentro de su identidad y alcance. Conservar STOP, revocación, permisos vigentes y comprobaciones por efecto; persistir una elección no convierte un token temporal en autorización permanente.
- Detectar los enlaces web en el propio mensaje humano. No exigir otro cuadro de texto para copiar o editar URL. Mostrar los sitios detectados y, si hace falta ampliar el alcance, un control concreto ligado a esa solicitud.
- Los controles que pertenecen a una respuesta u operación aparecen dentro del propio mensaje/tarjeta que la propone: aceptar un permiso, aceptar y ejecutar un plan, rechazar/cancelar, revisar, copiar, editar, fuentes y traza. Vincularlos a la identidad y revisión exactas del mensaje/operación. No trasladarlos a un panel global ambiguo.
- Los controles persistentes de conversación, como modelo y preferencia de lectura web, permanecen junto al compositor. No confundirlos con la aceptación de una operación concreta.
- El aviso informativo de lectura web no ocupa el compositor. Tras activar su tick, mostrarlo una sola vez dentro de la primera respuesta nueva recibida de ese contexto, en un recuadro ámbar de advertencia. OFF seguido de ON constituye otra activación. No repetirlo en cada mensaje ni afirmar que se ha leído una página por mostrar el aviso. Conservar el tick junto al compositor; ON sin sitios permite chat normal y no concede lectura web hasta disponer de alcance válido.
- Todos los flujos deben poder realizarse desde el chat sin cambiar de ventana o sección: pedir, elegir/configurar, preparar, revisar, autorizar, ejecutar, comprobar y recuperar evidencias. Reutilizar paneles dentro de los mensajes/tarjetas correspondientes; no forzar navegación a Agentes, Tareas, Permisos, Archivos o Configuración para completar un flujo. Mantener los otros accesos como alternativas. Esta es una condición de aceptación transversal; un flujo todavía externo se registra como pendiente.
- Una aceptación válida continúa sin otra confirmación redundante; una modificación de texto, plan, destinatario, raíz, alcance o revisión invalida las aceptaciones correspondientes.

Esta decisión define comportamiento requerido, no acredita implementación ni pruebas. Los handoffs y evidencias anteriores se conservan como históricos; verificar cada superficie modificada antes de declararla conforme.

