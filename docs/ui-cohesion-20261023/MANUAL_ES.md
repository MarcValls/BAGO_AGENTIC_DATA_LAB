# Interfaz BAGO: sistema visual común

La interfaz comparte fondo azul oscuro, superficies de trabajo y elevación reservada para diálogos y menús. Los acentos identifican selección, foco y acciones. Los estados siguen incluyendo texto; un color de integridad no significa PASS del producto.

## Chat y biblioteca

«Conversaciones y agentes» abre la biblioteca sobre todo el interior del chat. El cierre manual recupera mensajes, borrador y modelo. «Nueva» crea una conversación vacía, cierra la biblioteca y enfoca el cuadro de escritura; no envía mensajes. Si la creación falla, conserva el chat y muestra el error.

Usuario y asistente mantienen tarjetas distintas. Copiar y Editar pertenecen al mensaje donde aparecen; el botón derecho abre las acciones de ese mismo mensaje. Editar sólo aparece cuando el mensaje lo permite. «Gestionar agentes» es una acción secundaria de la cabecera Agentes.

## Inspector

Abre el Inspector desde el menú lateral para consultar la conversación actual. Se muestra su ID completo y la ejecución predeterminada asociada; sin ejecución, los contadores quedan a cero. La demostración histórica se elige expresamente y es independiente del chat. «Salir» está al final de la barra lateral del Inspector y devuelve el foco a su acceso.

## Servicios y configuración

Comunicaciones, Contactos, Espacio de trabajo, Agentes y Capacidades usan los mismos planos y separadores. Configuración conserva el selector Español/English. La apariencia no activa servicios ni concede permisos; las confirmaciones de escritura y acciones externas siguen vigentes.

## Instalación y vuelta atrás

Descomprimir el ZIP en una ubicación nueva, comprobar DELIVERY_SHA256SUMS.json y seguir README_ES.md del paquete Docker. `python dev.py preflight`, `python dev.py build`, `python dev.py up` y `python dev.py test` usan la configuración declarada. El backend, sus datos y las credenciales no se incluyen. La referencia al backend existente debe configurarse; no copiar registros de proveedores.

La actualización local del canal8093 se realiza sólo tras aceptación independiente. Se conserva la configuración e imagen RC4 de vuelta atrás; no borrar volúmenes ni bases de datos. El informe de entrega registra imagen, hashes, montajes y pruebas del candidato instalado. La observación visual no demuestra ejecución de modelos ni envío por WhatsApp.
