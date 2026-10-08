# BAGO AGENTIC DATA LAB · Manual 01 · edición v1.2

## Titularidad y finalidad

Este manual pertenece al proyecto **BAGO AGENTIC DATA LAB**, no al proyecto educativo IA. LA PREGUNTA. La maquetación anterior se utilizó como punto de partida visual, pero la presente edición identifica correctamente el producto y su ámbito de uso.

**Título:** Manual para dummies: cómo leer una ejecución.

**Alcance:** uso didáctico de Decision Inspector, LocalTrace, Actions, recibos y Jaeger local. Las cinco lecciones y el manuscrito fuente se mantienen sin cambios doctrinales.

## Qué contiene

- `BAGO_ADL_MANUAL_COMO_LEER_UNA_EJECUCION_v1.2.pdf`: manual final, 9 páginas A4.
- `PREVIEW_CONTACT_SHEET.png`: todas las páginas para revisión visual.
- `MANUAL_PARA_DUMMIES.md`: fuente original preservada byte a byte.
- `manual.html`, `estilos.css`, `build_manual.py`, `requirements.txt`: edición reproducible.
- `MANUAL_PARA_DUMMIES_assets/`: cuatro capturas originales completas.
- `overview_recorte.png`, `trace_recorte.png`, `actions_recorte.png`, `jaeger_recorte.png`: recortes exactos incluidos en el PDF.
- `QA_MAQUETACION.md`: controles editoriales y límites de validación.
- `MANIFEST.json`, `SHA256SUMS.txt`: inventario y huellas de archivos.

## Reproducción

Desde la carpeta de este paquete:

1. `python -m pip install -r requirements.txt`
2. `python build_manual.py`

La reproducción depende de que haya disponibles las mismas fuentes o fuentes métricamente equivalentes; después debe comprobarse la salida visual.

## Qué cambia frente a la versión editorial anterior

- Propietario documental y nombre de entrega: **BAGO AGENTIC DATA LAB**.
- Portada, cabeceras, metadatos y paleta: alineados con la identidad oscura/azul del producto.
- Capturas, datos técnicos, recorrido, advertencias y comandos: sin alteración.
- El manual deja de presentarse como material perteneciente a IA. LA PREGUNTA.

## Límite de evidencia

La revisión certifica exclusivamente la maquetación. No certifica nuevas ejecuciones, autorizaciones, recibos, servicios remotos ni envíos a AWS.

**Estado:** edición corregida lista para sustituir el PDF anterior.
