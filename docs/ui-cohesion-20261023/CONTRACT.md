# Cohesión visual BAGO

Orden vigente: unir visualmente las pantallas; evitar apariencia de piezas superpuestas. Conservar ángulos rectos, baja carga cognitiva y todo el ancho útil. Se conservan las fuentes y evidencias RC7 sin atribuirle esta mejora.

## Aceptación finita

Tres superficies comunes: fondo base, área de trabajo y elevada para diálogos/menús. Una agrupación tiene un marco; contenido interior separado por espacio o línea tenue. Una escala de espaciado y tipografía. Acento cian/azul común para selección/foco; conservar colores y texto semánticos de error, autorización, disponibilidad e integridad. Degradado reservado a cabecera principal, sin acumular sombras en tarjetas.

UC01: capa canónica compartida frontend/src/VisualSystem.css, importada una sola vez desde App.tsx tras ServiceSurfaces.css. Adaptadores explícitos de selectores existentes para shell, páginas de servicio/agentes/capacidades, tarjetas genéricas y anidadas, chat/biblioteca/composer e Inspector/Settings. CSS sólo: sin cambiar permisos, API, datos, handlers, orden de foco, overflow, display, tamaños de panel o breakpoints existentes. Evitar !important, selectores universales que borren estados y pseudo-contenido informativo. Los colores de usuario/asistente y estados se conservan. No modificar fuentes congeladas anteriores; before/delta explícitos y pruebas de alcance.

UC02: empaquetar sucesora desde fuentes congeladas, frontend completo y build sobre ZIP extraído. Observación visible acotada: Chat+mensajes, biblioteca completa, comunicaciones sin datos personales, contactos vacíos o datos ocultos, workspace, agentes, capacidades, Inspector y Settings. Capturas actuales, sin teléfonos/nombres de contactos ni tokens. No enviar mensajes ni ejecutar modelos. Wide y estrecha para biblioteca/Inspector; evitar matriz en bucle. Comprobar Nueva/cierre/foco, preservación de borrador, scroll y Salir; identidad y evidencia conservadas. README generado según AGENTS. No aplicar8093 hasta UC03PASS; mantener rollback RC4 y proveedor/API/datos.

UC03: revisión independiente de fuentes, ZIP, logs y capturas. Separar datos heredados de ejecución nueva, P0/P1 bloquean. Aprobación acotada no equivale a validar capacidad genérica agent.run, proveedores externos ni experimento Sollutia. Publicación Git no forma parte de este cierre.
