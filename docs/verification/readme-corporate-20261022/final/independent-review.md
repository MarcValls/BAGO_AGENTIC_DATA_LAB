# Revisión independiente de la candidata corporativa

**Resultado: PASS**, limitado a documentación y evidencia local identificadas abajo. No declara corregida la conexión Chat → Inspect ni sustituye las pruebas de integración que ejecuta el coordinador.

## Candidata observada

- Identidad del alcance facilitada por el coordinador: `7572a15b64bebe005b6cdfa470c58b29497d264781cc876e9e994f365fa051c2`.
- README SHA-256: `e2562629dd142f9e6c8cf050d6852058e4cf88f17903c2f91891c1c8a8d337fc`.
- 23 archivos del alcance leídos y sus hashes conservados en [independent-review.json](independent-review.json).
- Revisión de solo lectura sobre el worktree. Ningún archivo de la candidata modificado.

## Observaciones ejecutadas

| Comprobación | Resultado | Alcance |
|---|---|---|
| Portada corporativa y navegación | PASS | Banner BAGO SVG local, identidad consistente, tabla de navegación, Chat como entrada principal |
| Organización | PASS | 14 secciones principales visibles y 14 accesos propios «Profundizar»; 354 líneas visibles, 728 totales, sin límite compacto |
| Enlaces locales | PASS | 212 referencias locales comprobadas, sin archivos ni anchors ausentes |
| Estructura Markdown | PASS | 7 bloques details equilibrados; 5 Mermaid con etiquetas entre comillas; históricos en apéndices, contenido principal visible |
| Capturas | PASS | 5 PNG de 1920×978 inventariados; hashes y dimensiones recalculados; 4 se presentan en la galería |
| Contraste visual de imágenes | PASS | Se inspeccionaron chat.png e inspect.png: respuesta con DEMO-001/002, citas y ALLOW; Inspect muestra otro ID de traza |
| Evidencia del chat | PASS documental | Perfil nuevo, lectura autorizada y respuesta ligados al fixture y traza; la creación y la respuesta tienen horas separadas |
| CI | PASS documental | Registro y resumen coinciden en commit64a88f, fecha y URL. Baterías550/127/49/13 separadas, sin suma ni atribución al README nuevo |
| Límites de producto | PASS documental | Cobertura parcial desde Chat, controles manuales, proveedor efectivo y ejecución de herramientas separados; ninguna afirmación de funcionalidad total |

## Hallazgo de producto conservado

**CHAT-DEMO-001 sigue FAIL:** el chat nuevo produjo `trace-496fac766f384348`; Inspect muestra Bruma `trace-5b385699ffda0529`. El texto lo señala en galería, demostración, observabilidad, guía frontend y procedencia. El PASS de una evaluación anterior no se atribuye al nuevo chat. La demostración nueva acredita lectura y respuesta en el runtime observado; no pagos, ejecución genérica, aprendizaje continuo ni coste gratuito.

El esquema del frontend presenta un recorrido conceptual hacia Inspect. Sus tablas y las advertencias expresas precisan que no se ha demostrado la conexión automática de la conversación nueva. No se detectó una sobreafirmación que impida aprobar la documentación dentro de este alcance.

## Límites y cierre

- **NOT_RUN por este revisor:** suite completa, repetición del navegador y render de GitHub. La ejecución completa y la consistencia final corresponden al coordinador; no se lanzaron pruebas paralelas.
- La comprobación de enlaces es local, no una consulta HTTP de cada URL externa.
- Los nuevos assets y documentos existen pero deben incluirse al publicar. Antes del push se debe comprobar el inventario del commit y conservar todos los 23 archivos del alcance.
- Este informe no cambia la candidata congelada. Si cambia cualquier fuente después de esta observación, debe renovarse su identidad y repetirse la verificación afectada.
