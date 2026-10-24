# Orden actual: autor y acciones de cada mensaje

El usuario pide distinguir mensajes de usuario y asistente, anclar visualmente Copiar/Editar al recuadro correspondiente y ofrecer esas acciones en menú contextual de botón derecho. Se conserva Salir en sidebar y biblioteca hasta media altura.

Esta orden explícita amplía la integración EX02 mediante delegación nativa `/root/chat_message_actions` con rol decision-ui-engineer. Scope de escritura delegado exclusivamente: `frontend/src/components/AgentChat.tsx`, nuevo `frontend/src/components/ChatMessage.css`, nuevo `frontend/tests/ui/chat-shell/message-actions.test.tsx`, `docs/inspect-exit-20261023/messages/**`. Root EX02 consume su handoff materializado y contrasta hashes/pruebas; EX03 revisa ambos addenda y EX01. No se modifica ni se vuelve a firmar el handoff congelado EX01. La misión original y las ampliaciones explícitas se conservan separadas para no ocultar cambios de alcance.

Contrato de aceptación:

1. Cada artículo contiene autor, contenido y sus acciones en un mismo recuadro. Roles diferenciados por etiqueta y composición/alineación/borde, sin depender sólo del color.
2. Acciones inline ancladas. Menú contextual por botón derecho y teclado ContextMenu/Shift+F10; cierre Escape/clic exterior y retorno de foco. Posición contenida en viewport.
3. Copiar y Editar ejecutan los handlers existentes sobre el mensaje exacto. Sólo se ofrece edición cuando ya era elegible. Ningún permiso, llamada API, acción de modelo o edición histórica nueva.
4. Cambiar conversación o desaparecer mensaje invalida menú antiguo. ES/EN reutiliza claves existentes sin alterar payload ni contenido del usuario/agente.
5. Pruebas positivas y negativas focales, build, fuentes congeladas y handoff. Root observa en Brave real recuadros, acciones y menú de mensajes distintos, amplio y estrecho acotados. Comprobar copia exacta sin exponer otros datos; editar sólo prepara el composer y se limpia sin enviar.

No construir ni probar sucesivas imágenes obsoletas. La nueva candidata final se prepara después de ambos freezes; RC1 preparada se conserva NOT_RUN. El frontend completo se prueba una vez en el ZIP final extraído. El generador Python ya ejecutándose no se reinicia; registrar identidad conservada de sus fuentes y limitación temporal si su terminación precede la última edición CSS/TSX. Ningún resultado del paquete predecesor se declara ejecución nueva del final.
