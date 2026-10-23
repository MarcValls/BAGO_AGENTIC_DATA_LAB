# BAGO · Inspector: conversación e identidades

## Entrar

Abre Inspector desde el chat. La fuente inicial es **Conversación actual** y la ejecución más reciente de esa conversación ya está seleccionada. Sin ejecuciones aparecen cero registros y un estado vacío.

## Identificar

El recuadro de conversación muestra el identificador completo. **Copiar ID** lo copia sólo al pulsarlo; la interfaz confirma la copia o informa del fallo. Ejecución, traza e integridad son campos distintos. **Hash comprobado** acredita la integridad del archivo registrado, no una evaluación PASS ni autorización para actuar.

## Profundizar

El desplegable de datos técnicos conserva los códigos originales, SHA-256 y límites del servicio. Las métricas cuentan registros observados. Cambiar el selector de fuente a **Demostración histórica** es una acción explícita: sus datos son independientes del chat actual.

## Idioma

Configuración permite Español o English y conserva la preferencia. Cambiar de idioma no cambia la identidad de conversación ni ejecuta un modelo.

## Instalar la candidata

El paquete incluye `LEEME.md` con Docker y `context-public/repository/docs/agent-write/MANUAL_ES.md` para la escritura revisada y su CLI independiente. Conserva la versión anterior antes de cambiar de candidata. La API y sus proveedores siguen perteneciendo al canal del host; el paquete no incluye credenciales ni conversaciones.

Las pruebas y capturas se entregan con sus identidades y alcance. Una instrucción de este manual no es un recibo de ejecución.
