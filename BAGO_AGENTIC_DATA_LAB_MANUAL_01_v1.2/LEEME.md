# BAGO Agentic Data Lab · Manual 01 · edición 1.3

Actualizado el 15 de octubre de 2026. Esta edición revisa la ruta actual de acceso a Decision Inspector, el launcher local, el recorrido de evidencias y recibos, y la reproducción opcional de Jaeger.

## Archivos

- `BAGO_ADL_MANUAL_COMO_LEER_UNA_EJECUCION_v1.3.pdf`: documento final.
- `MANUAL_PARA_DUMMIES.md`: fuente editorial.
- `manual.html`, `estilos.css`, `build_manual.py`: fuente HTML, estilos y generador.
- `MANUAL_PARA_DUMMIES_assets/`: capturas de referencia tomadas el 8 de octubre de 2026.
- `PREVIEW_CONTACT_SHEET.png`: vista de todas las páginas del PDF.
- `QA_MAQUETACION.md`: controles de maquetación y límites de revisión.
- `MANIFEST.json`, `SHA256SUMS.txt`: inventario y hashes del paquete.

## Reproducir

Desde esta carpeta ejecuta `python build_manual.py`. Requiere Pillow y PyMuPDF para crear la hoja de contacto. Para PDF usa WeasyPrint si está instalado; de lo contrario usa Microsoft Edge en modo headless.

Las capturas no se pudieron refrescar: la aplicación y Jaeger no estaban activos al preparar esta edición. El contenido operativo se contrastó con el código y la documentación del repositorio a 15 de octubre de 2026. La guía no afirma que se haya ejecutado una nueva demo ni una nueva validación de Jaeger.
