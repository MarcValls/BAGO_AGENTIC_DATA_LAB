# README minimalista — candidata para revisión

Objetivo: materializar la portada de la PR #102 en el generador, sin fusionar
hasta que Marc acepte el resultado visual. Alcance: documentación; no modifica
la aplicación, sus permisos, contratos de ejecución ni fuentes de estado.

## Implementación

- `render_svg_landing()` admite v3 editorial y mantiene v2 con su renderizador.
- El manifiesto conserva los nueve SVG y toda su validación de seguridad.
- Cuatro accesos iniciales, cuatro áreas, recorrido gobernado, captura fechada,
  instalación, demo y enlaces a arquitectura, GEX, seguridad, estado y evidencia.
- Párrafos breves para las áreas permiten ajuste natural en pantallas estrechas.
- Las rutas Markdown también rechazan escapes mediante enlaces simbólicos.
- `render_readme()` no se modifica; la guía completa conserva sus bytes.

## Evidencia visual

[Captura real de GitHub en escritorio](github-desktop.jpg), tomada el 29/10/2026
sobre `a30cc743335f997e9f2f8f7e15a82d04418954f3` en la rama de previsualización
`codex/readme-minimal-candidate-20261029`. El README observado es idéntico al
README de esta candidata; las modificaciones posteriores son pruebas y documentación.

Viewport: 1363 × 936. Captura de página completa. Observación: título y propuesta
legibles, cuatro accesos antes de las áreas, ningún acordeón, imagen cargada
(1920 px originales; 993 px renderizados), fecha y límites visibles. Ancho del
documento 1348 px, inferior al viewport: sin desbordamiento horizontal observado.

**PASS:** render GitHub de escritorio y carga de la imagen.
**NOT_RUN:** revisión móvil/estrecha real. La API de este navegador no expone
redimensionado ni emulación móvil. No se presenta un recorte como prueba móvil.
**PENDIENTE:** aceptación visual humana. No fusionar ni activar auto-merge.

## Conservación

`conservation.json` compara 34 archivos con la base: README_DETAILS, vista previa,
manifiestos técnicos/visuales, todo `.bago/canon/` y SVG bajo `docs/assets/`.
Todos conservan exactamente los mismos bytes y SHA-256. La única documentación
existente adicional que se adapta es el contrato propietario de generación.

## Reproducción

Desde la raíz, con Python y Node disponibles:

```sh
python -m pip install -r requirements-test.txt
npm ci --prefix frontend
```

El entorno de pruebas necesita muestreo OTel completo; el host de esta sesión
hereda un muestreo del 1 %. Se ajusta únicamente para el comando de generación:

```sh
OTEL_TRACES_SAMPLER=always_on OTEL_TRACES_SAMPLER_ARG=1 python scripts/generate_dynamic_readme.py
python scripts/generate_dynamic_readme.py --check --skip-tests
```

PowerShell equivalente para la generación, restaurando después el entorno:

```powershell
$previousSampler = $env:OTEL_TRACES_SAMPLER
$previousSamplerArg = $env:OTEL_TRACES_SAMPLER_ARG
try {
    $env:OTEL_TRACES_SAMPLER = 'always_on'
    $env:OTEL_TRACES_SAMPLER_ARG = '1'
    python scripts/generate_dynamic_readme.py
    if ($LASTEXITCODE -ne 0) { throw 'FAIL: generación completa' }
    python scripts/generate_dynamic_readme.py --check --skip-tests
    if ($LASTEXITCODE -ne 0) { throw 'FAIL: consistencia' }
} finally {
    $env:OTEL_TRACES_SAMPLER = $previousSampler
    $env:OTEL_TRACES_SAMPLER_ARG = $previousSamplerArg
}
```

La primera generación de arranque usó `--skip-tests` para actualizar el artefacto
que las pruebas comparan con el renderizador; ese paso es NOT_RUN respecto a la
suite y no sustituye la generación completa. La colección no constituye PASS de tests.

El primer intento completo produjo **FAIL: 37 failed, 1707 passed, 2 skipped**
(`generation-initial-fail.log`). Los fallos correspondían a muestreo OTel y a
la ausencia de jsdom. Tras instalar las dependencias declaradas y usar muestreo
completo, el retest de esos módulos produjo **146 passed**
(`environment-retest.log`). No se alteró código de esos módulos.

Las 49 pruebas del README pasan (`focused.log`). La última ampliación de la
aserción de enlaces obligatorios se verificó además con las 17 pruebas del
módulo minimalista. Los resultados finales y las identidades están en `RESULT.json`.

## Continuación

1. Revisar README renderizado en GitHub con viewport móvil real (p. ej. 390 px),
   enlaces iniciales, ajuste del flujo, imagen y pie documental.
2. Registrar captura, dimensiones, SHA y resultado; resolver cualquier defecto.
3. Obtener aceptación visual explícita de Marc antes de salir del estado candidata.
4. Revisar CI sobre el HEAD final. Esta PR no fusiona ni promueve la propuesta.
