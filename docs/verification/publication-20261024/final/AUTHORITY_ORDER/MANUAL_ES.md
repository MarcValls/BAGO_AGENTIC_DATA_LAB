# BAGO · orden de los controles y las áreas de trabajo

La barra lateral presenta **Configuración → Espacio de trabajo → Chat → Agentes → Capacidades → Comunicaciones → Inspector**. Manual permanece accesible. Chat sigue siendo la pantalla inicial. Configuración utiliza el mismo control, ahora arriba; el pie conserva el control de plegar la barra.

El orden expresa precedencia de controles, contexto, trabajo, servicios y supervisión. No crea una nueva cadena de permisos. Workspace no pasa a ser propietario global de agentes; el chat no obtiene ejecución universal. El Inspector permite revisar y conserva sus controles. El goal anterior de títulos estrechos sigue pausado.

Configuración conserva sus paneles, selector Español/English y mecanismos de cierre y retorno del foco. Agentes conserva sus submenús. Comunicaciones conserva Mensajes, Historial y Contactos, con sus formularios, permisos y confirmaciones. Abrir el grupo sólo despliega sus destinos. Entre sus tres destinos se mantienen los cambios locales; al salir del grupo se aplica el comportamiento anterior, sin prometer persistencia de borradores no guardados después de reiniciar.

## Reproducción visual

1. Abre la candidata y comprueba que la pantalla inicial sigue siendo Chat.
2. Revisa el orden lateral y abre Configuración; cambia Español a English y vuelve a Español. Cierra el panel y comprueba el retorno al mismo control.
3. Abre los grupos Agentes y Comunicaciones; utiliza sus destinos por nombre y comprueba el indicador de selección. No guardes ni envíes nada para verificar la navegación.
4. En Mensajes, prueba texto sintético sin guardar, alterna Historial y Contactos y vuelve. Los campos permanecen. No necesitas crear contactos ni vincular Google.
5. Comprueba la disposición estrecha y el acceso con teclado. La barra puede desplazarse; los controles siguen accesibles.

Las capturas nuevas corresponden a esta candidata; los registros de RC10 son antecedentes separados. Las bibliotecas y campos sensibles se enmascaran antes de guardar las imágenes. No se presenta una captura como ejecución de un servicio.

## Instalación y vuelta atrás

Extrae el ZIP en una ubicación nueva, verifica **DELIVERY_SHA256SUMS.json** y abre **LEEME.md**, la entrada real del paquete. Consulta `python dev.py preflight` antes de `build`, `up` y `test`. El paquete contiene el frontend y fuentes públicas; la API8094/sesión del host se conserva como dependencia explícita. No incluye credenciales, datos de usuarios ni registro de proveedores.

Prueba primero un puerto libre y datos aislados. Para volver a la anterior candidata conserva su ZIP y configuración de imagen/montajes, detén únicamente los servicios de esta candidata y restaura la configuración anterior. No borres volúmenes ni atribuyas a un rollback efectos que no revierte.

## Capacidades pendientes

Este cambio no amplía el catálogo estático de seis tarjetas ni conecta MCP genérico, sandbox o agent.run. El diagnóstico y plan de registro único/asignación efectiva están separados en authority-design/CAPABILITIES_PLAN.md. Las herramientas del host utilizadas para desarrollar ADL no se convierten automáticamente en herramientas invocables por el producto.
