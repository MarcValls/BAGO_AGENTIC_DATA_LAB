# Bruma Market — demo de cliente ficticio

Vídeo explicativo de un caso de atención de pedidos exprés con más de 24 horas de retraso. Las pantallas son una composición visual basada en la evidencia local citada abajo; no son una grabación de una sesión en vivo.

## Artefactos

- Vídeo MP4: `bruma_market_demo_v1.mp4` (68.0 s, 1920×1080, sin narración de audio).
- Subtítulos en español: `bruma_market_demo_v1.es.srt`.
- SHA-256 MP4: `bebb95aebe77bed4f303a1eb81d3170d850e79f7c5de0eeab5075187beca6460`.
- SHA-256 fuente de evidencia: `3c12344fd5cb0676538c81b60fce1c3eab5b3d9f8124f4aa3f2974caf527db54` (`evidence/public_e2e_demo.md`).
- Renderizador reproducible: `scripts/render_bruma_market_demo_video.py`.

## Alcance demostrado

Bruma Market es ficticio. La demo describe recuperación de dos fragmentos de fixture, la regla de devolución del coste del envío exprés, su validación QA, y un recorrido local con sandbox, recibos y evaluación estructural PASS.

Es una composición basada en `evidence/public_e2e_demo.md`, no una llamada a un proveedor remoto ni una transacción real. AWS live y OpenMetadata live permanecen `NOT_RUN`; la evaluación PASS comprueba estructura y enlaces de evidencia, no la calidad general de un modelo ni preparación para producción. Los datos son fixtures locales y la demo no contiene datos de clientes reales.
