# Orden final: tres submenús, sin pestañas duplicadas

Sustituye el contrato anterior de sólo Contactos antes de comenzar su implementación. La misión de Inspector sigue PAUSED, con bytes preservados y fuentes activas devueltas a RC9. No se reanuda.

## Jerarquía solicitada

Comunicaciones (grupo desplegable como Agentes)
— Mensajes
— Historial
— Contactos

Retirar las tres pestañas superiores de Comunicaciones. Mensajes e Historial navegan al contenido existente de Communications; Contactos abre la pantalla completa Contacts que antes estaba en primer nivel. Reutilizar destinos y controles, no duplicar formularios. El grupo sólo despliega; no envía, guarda ni navega al abrirse. Contactos no queda en primer nivel. Selección activa, sidebar compacta, móvil y teclado funcionan como en Agentes.

## Contrato de integración congelado para paralelo

CS02 expone prop opcional `activeSection?: 'message'|'history'` en Communications, por defecto `message` para consumidores externos/inline. Sin ServiceTabs superior ni Contacts embebido. Secciones internas conservan identidad accesible mediante aria-label, sin aria-labelledby apuntando a pestañas eliminadas. Sidebar de borradores sólo enMessage&&!inline. Los estados de formulario/calendario/revisión no se reinician al cambiar `activeSection`.

CS01 App mantiene Communications y Contacts montados dentro del grupo mientras se alternan sus tres destinos, usando paneles con hidden efectivo; así se conservan borradores locales y edición de contactos. No montar/activar destinos al sólo desplegar el grupo. Al salir del grupo se conserva el comportamiento global previo. Los enlaces y callbacks del chat a comunicaciones y de Contacts a usar destinatario se conservan. App añade vista `communications_history` para Historial; `communications` sigue siendo Mensajes y `contacts` sigue siendo Contactos.

CS02 debe hacer que el `initialContact` recibido desde el callback existente pueda seleccionar un destinatario al volver desde la pantalla Contacts sin borrar mensaje/calendario ya editados. Respetar busy/readonly, no aplicar cambios rechazados después automáticamente, no guardar ni enviar. Coordinar mediante pruebas, sin compartir archivos mutables entre agentes. La prop inicial sigue funcionando con un consumidor independiente.

CS01 sólo App.tsx, CommunicationsNavigation.tsx/.css y nuevo test ui/communications/communications-navigation.test.tsx, y sus dos etiquetas i18n si no existe plural adecuado. CS02 sólo Communications.tsx y tests de su comportamiento: nuevo service-tabs/communications-sections.test.tsx; actualizar service-tabs.test.tsx y ui/communications/communications.test.tsx sólo los casos afectados por la retirada explícita de pestañas. Antes/delta acotados y no borrar cobertura de preservación. Ninguno toca Inspector, Contacts, API/SDK o permisos. Estilos de paneles ocultos explícitos y consumidores del sistema visual común.

CS03 integra tras ambos handoffs/freeze, hace una ejecución frontend completa+build desde ZIP extraído y README por AGENTS. Demostración visible en misma sesión Brave: jerarquía sin entradas planas/pestañas superiores; cada destino real, estado de mensaje y contacto conservados al ir/volver; grupo/teclado/compacta/320px/ESEN. No contactos nuevos, envíos, modelos ni guardados. Capturas personales enmascaradas.

CS04 verifica de forma independiente. Tras PASS se aplica8093 conservando API8094/proveedores/volúmenes/rollbackRC9 y se observa. El goal anterior permanece PAUSED. Publicación Git y otras modificaciones fuera de alcance.
