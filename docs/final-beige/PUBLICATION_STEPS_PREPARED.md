# Publicación autorizada · pasos preparados

El usuario ha vuelto a autorizar sincronizar los cambios con GitHub. El destino sigue siendo una **rama de revisión y un PR borrador**, sin merge. Root hará el push. Estos pasos no ejecutan la publicación.

## Dependencias del último alcance

Esperar CL congelado, paquete RC15 y verificación independiente de su última preferencia. RC14 conserva sus resultados históricos; no acredita compactación del contexto. El controlador no dispone de amend: root autorizó conservar el CR y archivar el runtime exactamente para inicializar un sucesor explícito cuando se conozcan los archivos CL. No se cambian sus campos mediante funciones privadas.

## Gates de root tras revisión independiente

1. Terminar el sucesor P y su revisión independiente, con manifest final que relacione paths y SHA-256 del working tree. Conservar historia y datos locales; no incluir runtime, builds, dependencias, ZIP, galería23 o dumps privados.
2. Ejecutar `git fetch origin main` y registrar el SHA remoto real y código de salida. Comparar merge-base con ese SHA; si ha avanzado, actualizar la candidata y repetir las puertas afectadas. Leer una ref local sin fetch no demuestra frescura.
3. Con el Python disponible, ejecutar `publication_guard.py inventory --manifest <manifest-final> --output docs/final-beige/publication/INVENTORY.json` y después `scan` con otro recibo. Los marcadores se notifican con ruta/línea/tipo, nunca con el valor. Cualquier hallazgo requiere revisión; el scanner no modifica ni redacta fuentes.
4. Root prepara exclusivamente el índice autorizado; mantiene fuera los borrados de runtime y los cambios ajenos. Se conserva la normalización de texto excepto los once pins exactos. Ejecutar `publication_guard.py index` con otro recibo para comprobar **los blobs reales del índice**, diferenciando SHA del working tree, normalización e identidad Git. El script no escribe el índice. Con índice vacío devuelve NOT_RUN.
5. Root revisa diff e identidades, crea el commit, registra commit/tree y publica la rama y el PR borrador. No hacer merge. CI alojada seguirá NOT_RUN hasta que una ejecución real termine; no sustituir ese resultado por pruebas locales.

Los comandos `publication_guard.py` se ejecutan desde P, ruta `docs/final-beige/publication_guard.py`. No usar la allowlist propuesta de RC14 como manifest final de RC15: se actualizará después de las fuentes y pruebas finales. Los recibos se crean una sola vez y no se sobrescriben.

Los recibos que se escriben después del manifest son evidencia local posterior. Mantenerlos fuera del índice que verifican; no añadirlos después al commit como si ese índice anterior ya los incluyera. Root registrará su identidad por separado.

## Pruebas y límites que debe comunicar el PR

Separar **P1:941PASS/1SKIP y233 archivos protegidos**, **L:945PASS nuevos en RC14**, **RC14:476frontend/build y24visual**, y la futura evidencia RC15. No sumarlas ni presentar herencia como ejecución nueva. Mantener Google simplificado PROPOSED/sinOAuthlive, capacidades/autoridad efectiva pendientes, proveedores/WhatsApp reales NOT_RUN y goal Inspector pausado. Añadir aplicación y observación real8093 sólo si existen sus recibos propios.
