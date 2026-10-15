# Revisión editorial y de maquetación · Manual 01 edición 1.3

## Alcance revisado

- Rutas, controles y límites contrastados con `frontend/src/App.tsx`, `frontend/src/features/decision-inspector/`, `scripts/run-local-ui.ps1`, `docs/agent-chat-control/LOCAL_SETUP.md` y `docs/decision-inspector/FINAL_STATUS.md`.
- Se retiraron el puerto fijo 8082, la URL de repositorio personal, los IDs de ejecución presentados como actuales y los claims de UI ajenos al estado actual.
- La validación de 15 spans queda identificada como evidencia histórica del 8 de octubre de 2026.
- Se mantienen las cuatro capturas de esa fecha, señaladas como referencias visuales históricas.
- La interfaz y Jaeger no estaban activos durante esta edición; no se afirma una nueva captura, ejecución, traza o prueba live.

## Verificación mecánica

El generador crea HTML, PDF, hoja de contacto, manifest y hashes. Después de ejecutar `python build_manual.py`, comprobar:

- número de páginas, texto extraído y contenido requerido en el PDF;
- render visual de todas las páginas y ausencia de texto cortado o solapado;
- coincidencia de hashes en `SHA256SUMS.txt` y rutas listadas en `MANIFEST.json`.

## Estado

La revisión editorial está preparada. El estado final de maquetación se declara solo después de inspeccionar el PDF generado y la hoja de contacto de esta edición.
