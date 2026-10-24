# Inspector: identidad y salida

En Chat elige una conversación y abre Inspector. Se selecciona su ejecución más reciente; si no hay, aparecen ceros. La demo histórica sólo se consulta explícitamente y no sustituye al chat.

El ID completo se identifica en un bloque propio y puede copiarse con su botón. Ejecución, traza e integridad aparecen separados. Hash comprobado acredita integridad del archivo, no una evaluación PASS. El hash completo y los diagnósticos originales están en Datos técnicos originales.

Para volver al espacio de trabajo pulsa **Salir**, al pie de la barra lateral del propio inspector, o Escape. En inglés el botón es **Exit**. La cabecera del inspector ya no tiene X. La ventana de Configuración conserva su cierre propio.

En pantalla estrecha las vistas pueden desplazarse horizontalmente; Salir permanece en una zona separada debajo de ellas. Cambia el idioma desde Configuración. El idioma no cambia la conversación ni sus artefactos.

Instalación de prueba: extrae el ZIP en una carpeta nueva, sigue LEEME.md, valida `python dev.py preflight` y arranca frontend con el puerto explícito y el destino de API del entorno. El paquete no incluye credenciales ni sesiones. El README del repositorio, inventarios y evidencias identifican la candidata; una prueba anterior sólo se conserva con su alcance original.

En Chat, pulsa **Conversaciones y agentes** para desplegar la biblioteca sobre toda el área interior del chat. Las listas se desplazan dentro de esa superficie y el resumen permite volver a plegarla. Al cerrarla se recupera el chat. Abrir o cerrar la biblioteca no cambia conversaciones, agentes ni permisos.

Pulsa **Nueva** para abrir un nuevo chat: la biblioteca se cierra y el foco vuelve al cuadro de escritura. Si la creación falla, la aplicación debe mostrar el error; no debe afirmar que el chat se ha creado.

Cada mensaje muestra su autor y acciones dentro de su propio recuadro. Los mensajes del usuario se alinean a la derecha; los del asistente a la izquierda. Copiar obtiene el texto del recuadro correspondiente. Editar sólo aparece donde ya está permitido y prepara el borrador en el cuadro de escritura; no envía por sí solo.

El botón derecho sobre un mensaje abre sus mismas acciones. También puedes enfocar el recuadro y pulsar Shift+F10 o la tecla de menú contextual. Escape cierra el menú y devuelve el foco. Los campos editables de tarjetas embebidas conservan su menú nativo.

Las superficies de esta actualización conservan ángulos rectos y usan líneas de color y degradados discretos. El color apoya la jerarquía; el autor, la posición y el borde siguen identificando los mensajes. Un acento de integridad no convierte una traza en una evaluación aprobada.
