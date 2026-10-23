# Excepción autorizada de verificación —24 de octubre de2026

La planificación inicial limitaba esta preparación a una suite completa de la nueva candidata. La ejecución gestionada `d0c9b405f3174431b5b6d1fd1b555d00` terminó con10fallos,931PASS y1SKIP. El primer fallo era el README sin regenerar antes de que el generador comprobara su propia coherencia; nueve casos DOM carecían de la dependencia jsdom declarada en el checkout nuevo.

El coordinador autorizó explícitamente reparar esas dos causas de preparación: crear únicamente una unión ignorada de dependencias ya verificadas, preparar el README mediante el generador base con `--skip-tests`, comprobar los casos afectados y, sólo tras PASS focal, ejecutar **una segunda suite completa** con el mismo generador sin modificar fuentes de producto. No se modifica el entorno Python compartido.

Esta autorización posterior prevalece sobre el límite inicial de una ejecución; no permite más reintentos automáticos. El log y recibo fallidos originales permanecen inmutables. La aceptación reparada identifica los dos intentos y no suma resultados focales ni pases anteriores al conteo final.

No se cambia la misión ya iniciada durante una ejecución en curso, ni se reescriben sus recibos para presentar un FAIL como PASS. Los resultados posteriores pertenecen a su nueva ejecución gestionada y al estado preparado después de la corrección del entorno/bootstrap.
