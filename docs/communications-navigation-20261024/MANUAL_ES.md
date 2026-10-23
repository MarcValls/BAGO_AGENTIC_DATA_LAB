# Comunicaciones: navegación agrupada

En la barra lateral, abre **Comunicaciones**. Sus destinos son **Mensajes**, **Historial** y **Contactos**. Abrir o plegar el grupo no envía, guarda ni crea nada. Las pestañas duplicadas de la cabecera de Comunicaciones se retiran.

**Mensajes** utiliza el formulario existente, con borradores, destinatario, texto, adjuntos, calendario y revisión. **Historial** muestra las ejecuciones de mensajes existentes; no es todavía un registro general de cambios de contactos. **Contactos** abre la pantalla completa original: Agenda, edición e integración selectiva con Google. Los permisos, confirmaciones y límites anteriores permanecen.

Al alternar los tres destinos del grupo, se conservan los cambios locales de formularios. Usar un contacto como destinatario devuelve a Mensajes y conserva el texto/calendario; una operación bloqueada o de sólo lectura no obtiene permiso por navegar. No hay envío automático.

Teclado: Tab/Enter/Espacio activan botones; ArrowDown abre el grupo y mueve el foco al primer hijo; Escape pliega el grupo y devuelve el foco al encabezado. La barra compacta se expande para acceder al submenú. En pantallas estrechas el grupo mantiene sus destinos accesibles y selección visible. Español/English se cambia en Configuración.

El patrón futuro de historial por entidad se registra en HISTORY_PATTERN_PROPOSED.md. No se muestran filtros que impliquen eventos de contactos no registrados. Workspace, Chat y Agentes no se reorganizan en esta ronda. El goal de títulos del Inspector sigue pausado.

## Instalación y vuelta atrás

Descomprime la candidata en una ubicación nueva, contrasta DELIVERY_SHA256SUMS.json y sigue README_ES.md del paquete Docker (`python dev.py preflight`, `build`, `up`, `test`). El backend y credenciales no se incluyen; se usan las dependencias declaradas. Las pruebas y la aplicación local8093 se documentan separadamente con identidad de imagen/fuentes.

Se conserva RC9 y su configuración de montajes como rollback. No borres volúmenes ni bases de datos. Revertir la imagen/montajes no revierte ficticiamente operaciones ya realizadas. Esta actualización no requiere enviar, guardar contactos, ejecutar modelos ni cambiar proveedores para probar la navegación.
