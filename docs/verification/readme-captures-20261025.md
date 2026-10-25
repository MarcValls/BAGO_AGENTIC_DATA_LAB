# Capturas públicas y límites · 2026-10-25

Observaciones del **25 de octubre de 2026**. Esta selección editorial reúne cinco capturas reales ya existentes. No corresponde a una ejecución nueva ni demuestra el estado posterior de todas las funciones. La derivación para publicación conserva íntegros los cinco PNG; no reconstruye ni retoca pantallas.

## Qué muestra cada imagen

1. **03-jaeger-capability-selection.png**: selección/presentación de una capacidad en el asistente. La captura muestra un solo span; no es la ejecución del escáner.
2. **04-jaeger-delegation-denied.png**: una delegación fue denegada por raíz incompatible. La duración del hijo proyectado no se interpreta como medición nativa de una herramienta.
3. **05-jaeger-historical-long-chat.png**: un chat histórico duró aproximadamente 22 segundos y muestra doce spans. Una respuesta del proveedor no acredita ejecución de herramientas ni pruebas posteriores.
4. **08-jaeger-workspace-read-live.png**: lectura puntual autorizada de workspace en AgentChat, con ALLOW y catorce spans. Se observa la lectura entre dos rondas del proveedor. No se publica una precisión de microsegundos ni se afirma una misión documental integral.
5. **09-work-history-legacy-empty.png**: vista de Historial de trabajos **ANTES** de su corrección. El registro legacy consultado estaba vacío. Eso no demuestra que no existieran conversaciones, TaskRuns u otras ejecuciones, y no representa la vista reparada posterior.

## Integridad de las capturas publicadas

Las capturas de Jaeger son vistas de timeline sin argumentos, documentos ni payloads abiertos. La quinta imagen sólo muestra el panel legacy vacío. La selección excluye imágenes con títulos de otras conversaciones, rutas del equipo y detalles de proyectos ajenos al recorrido.

| PNG original publicado | SHA-256 |
|---|---|
| `03-jaeger-capability-selection.png` | `7b5f9e3a19406ed4a4374aa676464a318d5f25400ce73d5c87aa8ab4390dc261` |
| `04-jaeger-delegation-denied.png` | `81e6bb3b2e268f7487146f0ed6937df53083c7821c0c15f5102d5f21cc56b558` |
| `05-jaeger-historical-long-chat.png` | `d496ce191f0189cfb47a09a936493dcaed384e42211809fca5b82a35a4edd077` |
| `08-jaeger-workspace-read-live.png` | `f98750ea7d6bc49d60d8916ae8ed81e88d3e0411cb3ef791cb0a33d793e3fc93` |
| `09-work-history-legacy-empty.png` | `4ad58f619f37f8e274a5acebf19a16bbf96aee1699a52740cd3d3688ff425e1c` |

## Carrusel

El [visor HTML](../assets/readme-20261025/carousel.html) usa únicamente estas cinco imágenes locales y ofrece anterior, siguiente, pausa/reanudación y las teclas ArrowLeft/ArrowRight. Respeta la preferencia de movimiento reducido al arrancar. El [GIF de portada](../assets/readme-20261025/carousel.gif) se compuso mecánicamente con Pillow, a partir de estas mismas capturas, mediante ajuste proporcional y un fondo uniforme; no modifica los PNG ni añade resultados a la interfaz.

SHA-256 del GIF: `ccd68fa1f156cd057ce807c8cecf44e0ba709ecdae26ee010865f8620847f84b`. Tiene cinco fotogramas y un intervalo de cinco segundos por imagen. El HTML y el manifiesto canónico apuntan a la misma selección.

## Resultado y alcance de verificación

Una captura es evidencia de la pantalla observada, no un recibo de una ejecución nueva. Las trazas representadas corresponden a los casos descritos; la delegación denegada y la vista legacy vacía conservan su resultado negativo. No se afirma que las pruebas globales pasen, que el objetivo Jaeger esté cerrado ni que el candidato sea una release.

Esta guía es una derivación editorial nueva para la publicación WIP. Conserva la fecha de observación de las imágenes y su alcance histórico, sin copiar conversaciones, trazas JSON, recibos, corpus, configuración privada o rutas del equipo. El registro de CI seleccionado por el manifiesto mantiene su candidata y fecha propias; no valida automáticamente cambios posteriores.
