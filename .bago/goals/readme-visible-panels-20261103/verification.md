# Comprobación de la portada con paneles visibles

Base inicial: 9eba54aa248015df84383abf257c68a7062b3db5 (origin/main).

- Primera generación --skip-tests sincroniza los dos README sin afirmar ejecución.
- 26 pruebas específicas del README: PASS (focused-tests.log).
- Los nueve SVG aparecen como img dentro de README.md, no como enlaces a
  la galería: destinos, número de imágenes y ausencia de desplegables comprobados.
- Se conservan las cuatro entradas, áreas, captura histórica, fuentes y compatibilidad v2.
- No cambian los nueve SVG, README_DETAILS.md ni el runtime.
- Render visual en navegador GitHub: NOT_RUN; no se confunde la presencia
  del markup con comprobación del renderizado del host.

La solicitud de mostrar los paneles en la raíz sustituye su ubicación exclusiva
en la galería. Se mantiene la galería accesible y la generación desde fuentes.

## Resultado final local

- Generación con suite completa: PASS, 2113 tests pasados (full-suite.log).
- --check --skip-tests: PASS; 2116 recogidos, suite NOT_RUN en ese comando
  (readme-check.log).
- git -c core.whitespace=cr-at-eol diff --check: PASS. Se preserva CRLF
  preexistente del generador.
- Base remota refrescada antes de publicar: 9eba54aa248015df84383abf257c68a7062b3db5,
  igual a la base inicial.
- README_DETAILS.md y los nueve SVG sin cambios respecto a la base.

Publicación solicitada: main, mediante GitHub plugin y lease al SHA de base.
