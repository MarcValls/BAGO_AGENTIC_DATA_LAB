# Docker Dev — alcance y aceptación

Operación IMPLEMENTACIÓN en carpeta nueva. D01 inspeccionar reuso y Docker/WSL;
D02 exportar sólo código público y vincularlo mediante hashes; D03 construir
entornos Node22 y Python3.11/Pillow/ffmpeg; D04 ejecutar pruebas focales y build
frontend; D05 comprobar HTML/health/proxy hacia API host sin copiar proveedores;
D06 API con datos aislados y Jaeger opcional, puertos loopback; D07 patch nuevo,
manifiesto, instrucciones y evidencia. La falta de Docker sería NOT_RUN, nunca
un build PASS. El entorno actual sí tiene daemon Linux disponible.

Fuente ADL de partida: HEAD c5a78d33fbf5da608f550c4e8809eb6a8cb1be4c; se exportan
bytes seguidos por Git del working tree, con hash por archivo. Esto no equivale
a incorporar las fuentes nuevas de otras candidatas ni modificar main.

Puertas: config válido y sin puertos públicos/root mounts; imágenes construidas
con usuario no root; PNG/SQLite nuevos observados; pruebas Python focales y
frontend/build PASS; health frontend/API y proxy host GET realmente responden;
Jaeger aislado responde; ningún contenedor previo parado por esta tarea.
Manifest/patch deben poder verificarse sin instalar en un repositorio activo.

Fuera: instalación Docker/WSL, cambios en virtualización/firewall, push/remotos,
despliegue, Docker prune, migración de credenciales, inferencia de proveedor real,
WhatsApp/envíos, automatización de ventanas y promesas de UI renderizada sin
navegador. La sesión del host sigue siendo autoridad de los proveedores.

PROPOSED es intención; PREPARED identifica archivos; EXECUTED requiere comando;
VERIFIED exige recibo ligado a bytes; VALIDATED sólo se aplica a las puertas
que efectivamente pasen. Una puerta de build no valida otras capacidades.

## Identidad y aceptación de la integración I04

Los resultados RC1 externos permanecen históricos; esta integración no hereda su
validación por copiar archivos. El snapshot integrado admite nuevas fuentes sólo
mediante --include-snapshot y hash actual igual al handoff. No se exporta durante
la composición ni se reutiliza el ID20261023 para el conjunto nuevo.

La aceptación exige cobertura efectiva del watcher src/public, health503 si falta,
alta/edición/unlink público con efecto HTTP, HMR React existente/nuevo con estado
observado por root y recuperación tras error explícito, sin cambiar PID Vite ni
containerId. La repetición sobre fuente integrada identificada es obligatoria.
Una respuesta HTTP transformada no sustituye el DOM ni prueba conservación de estado.
