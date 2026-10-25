# WhatsApp en la candidata ADL · 25/10/2026

Estado del transporte automático: **reparación pendiente**. Esta nota acompaña la actualización del manual efectivo local; no declara una release ni cambia recibos históricos.

## Vincular la sesión

1. Abre Configuración → WhatsApp.
2. Escribe un nombre, habilita WhatsApp y guarda la configuración.
3. Pulsa Abrir navegador y vincular QR.
4. En el móvil, abre Dispositivos vinculados y escanea el QR de esa sesión.
5. Comprueba el estado y su fecha. Guardar la configuración o ver el navegador abierto no demuestra autenticación.

La sesión propia vinculada se conserva para BAGO. No publiques QR, cookies, credenciales ni datos de contactos.

## Cuando un envío queda incierto

El transporte de BAGO puede terminar como incierto mientras el mensaje sigue sin enviar en el editor de WhatsApp. Ese estado no demuestra envío ni recepción. Comprueba la conversación y el mensaje saliente exactos antes de actuar; no confirmes otra operación para repetirlo.

Si una persona autorizada completa el envío directamente en WhatsApp, registra esa acción y su comprobación por separado. El recibo incierto original de BAGO se conserva y no se presenta como un envío automático verificado. Un resultado leído en el caso observado no valida por sí solo el transporte de BAGO ni los próximos envíos.

## Evidencia y reparación pendiente

En el caso autorizado se observó el texto intacto en el editor y ningún saliente coincidente después del intento automático. El operador pulsó una única vez Enviar en la sesión visible; después se observó un único saliente coincidente, editor vacío y marca Leído. El destinatario y el contenido no se publican.

La inspección de código muestra que el transporte actual utiliza Enter como gesto de envío. La causa exacta por la que ese gesto no produjo el envío no está probada. La propuesta es verificar un único botón accesible de envío y mantener identidad de destinatario/texto, reserva durable, correlación del acuse y ausencia de reintentos. Implementación y pruebas de esa propuesta: NOT_RUN.

El manual efectivo local se actualizó para explicar esta limitación. El objetivo Jaeger y los fallos de integración permanecen abiertos; esta nota no altera sus gates.