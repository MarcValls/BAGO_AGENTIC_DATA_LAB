# Orden vigente: biblioteca ocupa todo el interior del chat

El usuario proporciona explícitamente `.window-panel-content` como área que debe ocupar la biblioteca abierta. Esta orden sustituye el máximo50% anterior. No se modifican sus evidencias históricas ni se presentan como aceptación del nuevo alcance.

FS01: al abrir `.chat-agent-panel`, su slot ocupa toda la superficie de `.window-panel-content`, en ancho y alto, con summary visible y scroll interno. Mensajes, herramientas y composer quedan cubiertos/ocultos e inaccesibles al teclado mientras la biblioteca esté abierta, sin desmontar ni perder sus datos/borrador/modelo. El cierre manual restaura el chat. Mantener detalles nativo, ángulos rectos, colores y accesibilidad.

Al pulsar Nueva (nuevo chat), ejecutar el flujo existente de creación, cerrar la biblioteca y enfocar el composer del nuevo chat. No inferencia ni envío automático. Conservar modo/proveedor y contratos actuales. Si crear falla, comunicar fallo visible; no fingir una conversación creada ni perder contenido anterior. Probar éxito y error, apertura/cierre, borrador preservado y ambos modos cuando corresponda.

Scope FS01: AgentChat.tsx, AgentChat.css, panel-height.test.tsx y nuevo panel-fullscreen.test.tsx; evidencia full-panel/**. Ningún otro CSS ni API/SDK/catálogo se modifica sin causa y aviso. Registrar before/delta y nuevas pruebas; actualizar test del antiguo máximo50% a la nueva orden explícita, preservando copia/hashes anteriores.

FS02: root integra fuentes finales en una nueva candidata después del freeze; ZIP previo RC5 conserva422PASS frontend pero no cubre este requisito. Comprobar extracción, prueba frontend completa y una observación amplia y320x700 acotada, scroll y Nueva reales. Mantener todos los cambios anteriores (Inspect identidad/Salir, mensajes/menú, coloresrectos, escrituras revisadas). README según AGENTS; no acumular conteos de pruebas repetidas. FS03 independiente antes de aplicar8093. API8094/DATA/proveedores se conservan. No modelo/WhatsApp/agent.run genérico.

Coordinación anterior NU queda supersedida durante NU02, sin aceptación terminal ni despliegue. Su runtime se conserva íntegro con mapa; NU01 y entregas de estilo permanecen evidencia de sus propias fases, sólo reutilizable mediante identidad y alcance explícitos.
