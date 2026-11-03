# Verificación editorial

Base inicial y comprobada de nuevo antes de publicar:
`bb1f3725d9d3881ca48c183a3499d957dfd9bade` (origin/main).

- Nueve SVG parseados y renderizados con CairoSVG 2.9.1. Revisión visual
  de conjunto; texto desbordado del panel 04 acortado y render revisado de nuevo.
- Destinos relativos de la galería comprobados contra archivos existentes: PASS.
- Se conserva la geometría, paleta y orden de los nueve paneles.
- Fuentes: guía frontend, STATUS e incidente CSV, diagnóstico optativo de
  ConversationStore, demo, GEX/BER y canon existentes en la base.
- No se han ejecutado UI, proveedores o consultas CSV como parte de este cambio.
- GitHub desktop/móvil y aceptación visual de Marc: NOT_RUN / pendiente.

Primer intento de generación: bloqueado por ausencia de pytest en el Python
predeterminado. Se usa el entorno existente /tmp/adl-sqlite-venv, con las
dependencias de pruebas instaladas; no se modifica el producto para resolverlo.

La comprobación de whitespace usa core.whitespace=cr-at-eol para preservar
los finales CRLF ya existentes del generador.

Primera suite completa: 39 FAIL, 2074 PASS, 3 SKIP, 114 subtests PASS
en 268,34 s. Log original: first-full-suite-failure.log.gz.
- 28 fallos de trazas coinciden con OTEL_TRACES_SAMPLER=parentbased_traceidratio
  y ARG=0.01 documentados anteriormente en el entorno.
- 9 fallos DOM requieren frontend/node_modules/jsdom, ausente.
- 2 fallos de README detectaron la portada aún anterior a la nueva fuente.

Preparación: npm ci --prefix frontend (PASS); generación --skip-tests
(PASS: 2116 casos recogidos, suite NOT_RUN) para sincronizar los archivos
antes de que los tests de reproducibilidad los comparen.
Segunda generación completa: OTEL_TRACES_SAMPLER=always_on,
OTEL_TRACES_SAMPLER_ARG=1, BAGO_DATA_ROOT no impuesto globalmente.
No se modifican pruebas ni expectativas.

## Resultado final

- Generación normal con suite completa: PASS, 2113 tests pasados.
  Evidencia: generation-pass.log.
- --check --skip-tests: PASS; 2116 casos recogidos, sin ejecución en ese comando.
  Evidencia: readme-check-pass.log.
- git -c core.whitespace=cr-at-eol diff --check: PASS.
- README.md revisado: área CSV y enlace a galería actualizados desde sus
  fuentes; README_DETAILS.md idéntico al de la base tras regenerar.
- Segunda consulta de origin/main inmediatamente antes de publicar:
  bb1f3725d9d3881ca48c183a3499d957dfd9bade, sin avance desde la base.
- src/, tests/ y frontend/ sin cambios respecto de la base.
- Estado editorial: IMPLEMENTADO y comprobado localmente; no se declara
  VALIDADO por Marc ni se acredita ejecución nueva de la aplicación.

La instrucción expresa del usuario incluye publicar en main. La aceptación
visual del usuario queda separada del permiso de publicación.

El log fallido se conserva comprimido sin modificar sus bytes originales;
los espacios de salida de pytest no son cambios de código.
