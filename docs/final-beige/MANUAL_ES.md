# BAGO · Configuración y acentos beige

## Qué cambia

Configuración vuelve a la parte baja de la barra lateral, con un contorno y acentos beige para localizarla. Los controles siguen siendo rectangulares. El resto conserva Espacio de trabajo, Chat, Agentes, Capacidades, Comunicaciones e Inspector; Chat continúa como pantalla inicial. Se mantienen las opciones Español/English y el retorno del foco al cerrar Configuración.

Los acentos visuales no conceden permisos ni conectan capacidades. Comunicaciones mantiene Mensajes, Historial y Contactos. Un borrador no es un envío aprobado. El catálogo dinámico de capacidades y nuevas asignaciones efectivas siguen pendientes de un contrato y verificación propios.

## Instalar para revisar

Extrae el ZIP RC14 en una carpeta nueva y comprueba `DELIVERY_SHA256SUMS.json`. Abre **LEEME.md**, la entrada real del paquete. El paquete contiene fuentes públicas e instrucciones; no sesiones, proveedores, bases de datos ni contactos de usuario. Docker debe disponer de contenedores Linux. La API del host en8094 es una dependencia existente y se mantiene aparte.

Primero ejecuta `python dev.py preflight` con la identidad indicada por el paquete. Utiliza un puerto libre para la revisión aislada. La batería frontend se ejecuta desde el ZIP extraído; no atribuyas a RC14 los resultados de RC13 ni los de otra instalación. Consulta los resultados y hashes de esta candidata cuando estén disponibles. Durante esta preparación, empaquetado, batería final, observación y aplicación están **NOT_RUN**.

## Recorrido visible

Comprueba Chat inicial, Configuración abajo y resaltada, apertura y cierre con retorno del foco, cambio Español/English y navegación por los grupos. Repite en ventana estrecha. No necesitas guardar contactos, enviar mensajes ni invocar proveedores para revisar este cambio. Las capturas deben ser nuevas y ocultar nombres, números, correos y datos privados antes de guardarlas.

## Aplicar y volver atrás

La aplicación sobre8093 exige validación independiente BS03 y comprobación de identidad del paquete.8094 y los volúmenes existentes se conservan. El aplicador guarda la configuración de RC10 para volver atrás y no borra volúmenes. Una orden de aplicación fallida puede haber cambiado el contenedor: consulta el registro; no se afirma una reversión automática. Una aplicación técnica debe completarse con observación visible del puerto real.

Mantén el ZIP anterior y sus evidencias. RC13 se conserva como candidata anterior, sin presentarla como respuesta final a la preferencia beige. El goal anterior del Inspector sigue pausado.
