# PLAN — README de entrada minimalista (ADL)

**Estado:** PROPUESTO · pendiente de aprobación visual, implementación y verificaciones  
**Fecha:** 2026-10-29  
**Base de planificación:** `main@fb80f9bf243e46090951d7a9da5f4ec84f4af656`  
**Previsualización:** [README_PREVIEW.md](../../../README_PREVIEW.md)  
**Alcance:** portada de GitHub, no rediseño de la app ni reemplazo de documentación canónica.

## Diagnóstico observado

El README actual funciona como una lista de `<details>` cerrados: «Mapa visual» y siete entradas de «Galería por tema». Al estar colapsados, el contenido relevante no aparece; el usuario ve un índice repetitivo con títulos extensos y poca información útil de primer nivel. En la captura proporcionada, también destaca el espacio vacío a la derecha: esto último depende de la composición de GitHub y no se puede eliminar con CSS propio desde un README.

**Evidencia de fuente:** `README.md` está generado por `render_svg_landing()` en `scripts/generate_dynamic_readme.py`; la configuración vigente es `docs/readme_svg_manifest.json` (esquema `bago.readme.svg.landing.v2`). `AGENTS.md` prohíbe editar `README.md` y `README_DETAILS.md` manualmente.

## Resultado visual esperado

1. Portada editorial sobria: titular y explicación breve, sin banners dominantes ni listas de acordeones.
2. Primera vista útil: empezar en Windows, demo local, arquitectura y evidencias como enlaces visibles.
3. Cuatro áreas funcionales con una línea descriptiva y acceso directo.
4. Flujo de ejecución gobernada legible en una sola línea.
5. Una captura real de UI con fecha y límites, visible sin desplegar.
6. La guía extensa y los recursos SVG existentes siguen disponibles en sus rutas originales.
7. Diseño nativo GitHub Markdown; sin HTML/CSS incompatible ni supuestos de pantalla completa.

## Contrato de contenido

- Una capacidad presentada como operativa debe tener un destino documental existente y delimitado; ni banners ni iconos pueden elevar `PROPOSED` a `VERIFIED`.
- `STATE.md` y los artefactos de evidencia siguen siendo fuentes de estado. No imprimir como «actual» un resultado de pruebas de otro SHA.
- Mantener visible el acceso a instrucciones de Windows, demo, contrato GEX, arquitectura, seguridad y `README_DETAILS.md`.
- Una captura debe estar etiquetada con su fecha; no sugerir que acredita el runtime del día.
- No eliminar SVG, manifiestos, fuentes documentales ni la generación de la guía completa como efecto lateral.

## Plan de implementación para Codex (solo después de aprobar el aspecto)

**P0 — Inventario:** refrescar `origin/main`, registrar SHA y contratos README; inventariar tests del generador y enlaces renderizados. Conservar baseline.

**P1 — Modificar fuente propietaria:** adaptar `render_svg_landing()` para producir el diseño de `README_PREVIEW.md`. Mantener manifiesto canónico para título, resumen y destinos, o versionar su esquema cuando cambie el contrato. No copiar y pegar a `README.md` directamente.

**P2 — Compatibilidad:** la portada `README.md` cambia, `README_DETAILS.md` continúa generándose íntegramente desde las fuentes actuales. Los SVG permanecen accesibles, aunque no sean el contenido dominante de la portada. No relajar validaciones de rutas, destino ni seguridad del manifiesto.

**P3 — Tests:** añadir o actualizar pruebas del renderizado para confirmar enlaces, ausencia de `<details>` en la portada, presencia de título/accesos/captura, salida determinista y resistencia a destinos inseguros. Revisar las pruebas existentes para evitar regresiones por expectativas del diseño anterior.

**P4 — Generar y contrastar:** ejecutar `python scripts/generate_dynamic_readme.py` (suite completa obligatoria según `AGENTS.md`) y luego `python scripts/generate_dynamic_readme.py --check --skip-tests`. No usar el segundo comando como sustituto del primero: `--skip-tests` solo recopila. Revisar diff de `README.md` y `README_DETAILS.md` y confirmar que el segundo no perdió secciones.

**P5 — Verificar en GitHub:** revisar la vista renderizada en desktop y móvil/estrecho, enlaces de la primera pantalla, contraste, dimensiones reales de la captura, lectura sin expandir componentes y ausencia de contenido que parece interactivo sin serlo.

**P6 — Entrega aislada:** PR separada de los cambios activos de Codex, comparar `main` antes de publicar, no fusionar automáticamente. Cierre con SHA, comandos, resultados y evidencia visual.

## Criterios PASS/FAIL

**PASS** exige: primera pantalla inteligible sin desplegables; acceso visible a cuatro rutas clave; enlace y procedencia de la captura; todos los destinos resueltos; README y README_DETAILS generados, pruebas y check PASS; ninguna regresión de documentación; inspección visual real.

**FAIL / BLOQUEADO** si el generador sobrescribe el diseño, se pierden destinos, un enlace está roto, se modifica el canon indebidamente, no se ejecuta la suite completa o el renderizado GitHub contradice la previsualización.

## Estado de este cambio

- **IMPLEMENTADO:** una vista previa Markdown independiente y este plan documental.
- **NO IMPLEMENTADO:** modificación del generador y la portada pública de `main`.
- **NO VERIFICADO:** pruebas automatizadas, render visual del futuro README y comportamiento del generador modificado.
- **NO MODIFICADO:** `README.md`, `README_DETAILS.md`, `docs/readme_svg_manifest.json`, código de aplicación.

## Regla de coordinación

Codex puede consultar este documento sin `checkout` de esta rama. No abandonar ni sobrescribir su tarea actual. Resolver divergencia con `main` antes de escribir; no crear otra fuente de verdad para el estado del proyecto.
