# Petición de usuario posterior: biblioteca hasta media altura

Autoridad: el usuario proporciona markup `.chat-agent-panel-slot > details.chat-agent-panel` y pide abrirlo «hasta mitad chat mas o menos». Se integra antes de aplicar la actualización. No se cambia el contrato congelado EX01, cuyos cuatro archivos permanecen intactos.

Trabajo de layout independiente asignado a inspect-ui (/root/failed_chat_ui), sin nuevo trabajo de decisiones/trazas ni cambio de coordinación: escritura exclusiva `frontend/src/components/AgentChat.css`, nuevo `frontend/tests/ui/chat-shell/panel-height.test.tsx`, `docs/inspect-exit-20261023/panel/**`. No App/SDK/API/proveedores/TSX. Guardar snapshot antes, cambio y prueba focal+build con identidad y handoff materializados.

Aceptación: apertura nativa del details permite ocupar aproximadamente media área del chat, máximo50% y sin mínimo de altura; el composer y mensajes conservan espacio. Summary fijo y scroll interno cuando el contenido supera lo disponible. Colapsado intacto. Comprobar una vista amplia y una estrecha reales en Brave existente, con medidas del panel y área dueña y capturas nuevas. No añadir redimensionador o instrucciones de interfaz no pedidos.

EX02 consume explícitamente la entrega de layout además de EX01. La candidata inspect-exit-20261023-rc1, ZIP SHA6026700004055bef7a05d697619065948a80780a006bfd3222bf5487c6c9668e, quedó PREPARED/EXTRACTED antes de este cambio: sus pruebas runtime son NOT_RUN. Se preserva y se prepara RC2 nueva; no se atribuirán resultados ajenos a RC2.

EX03 revisa ambas superficies y el paquete RC2 final. Mantener la comprobación de backend separada por identidad: esta adición cambia sólo CSS y una prueba TS. El generador Python de README ya en curso termina después de la integración; registrar su orden y fuentes Python conservadas. No reiniciar la suite completa mientras sigue en curso ni renovar la matriz responsive detenida. 8093 sigue RC4 hasta PASS independiente y observación posterior.
