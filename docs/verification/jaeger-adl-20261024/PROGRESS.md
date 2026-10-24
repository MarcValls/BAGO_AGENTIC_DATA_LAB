# Continuidad de Jaeger mediante BAGO ADL — 24/10/2026

Estado: trabajo abierto. Este documento registra progreso; no incorpora el código local ni certifica el producto.

## Alcance y procedencia
El usuario solicita conservar el chat como orquestador y efectuar los cambios de Jaeger mediante las capacidades de desarrollo de ADL. Codex prepara capacidades genéricas, opera controles y verifica externamente; esa preparación no se presenta como autoría nativa de ADL.
Base remota consultada mediante conector: 116cf67948184f070cb9d94508ee9ba59f7e878f. La instancia local aislada contiene cambios posteriores todavía sin publicar. Git por terminal falla al resolver github.com; el conector está disponible.

## Evidencia local histórica, no CI de esta rama
- Lifecycle 3A2 aplicado desde el panel ADL: dev_6e075ab54698400fa2892c8b72d73d62; patch 73556fb948ac4e3de8562d8fd18bef760c3e38b78bf6660f6699eb535171f5f2. Check ADL: 151 PASS.
- Provider 3B1 aplicado desde el panel ADL: dev_88c4d261778f4163bd6c4e0a71678cd3; patch a37505a25c6d2314b58fd4d120a4ff1df40e76bf1724134fd47c0ef97e6f261d. Check ADL: 156 PASS; revisión externa: 121 PASS y una prueba adicional.
- Primer chat observado en Jaeger: 46479ab451db0750f60934460e4acca2, 12 spans, profundidad 2. Es un chat de comprobación, no la misión documental final.
Los recibos permanecen locales: esta rama no los adjunta ni permite reproducir aún dichas comprobaciones.

## Pendiente y bloqueos
- El helper y los handlers de herramientas tienen una candidata PREPARED no aplicada: dev_efcdc3ae08314fc5a0f11685231817cd, patch ba4093130665808403b2bee62fc4b3f40ebd20a5908e891d9c9ffa7b7d07761e.
- Faltan asociación por invocación, compatibilidad de proyecciones, pruebas finales, revisión y aplicación desde el chat.
- Barra derecha: corrección solicitada a panel pegado al borde, WS e historial colapsables y reparto 50/50. Hay un P1 observado: una regla CSS posiciona todos los botones como la pestaña lateral e intercepta clics. No promover esa interfaz.
- Inspector: refactor local con checks anteriores, pendiente de verificación visual y de integración final.
- Tareas: propuesta Editar/Ejecutar, Revisar/Evaluar, Historial. Revisar debe conservar el resultado existente; lanzar nuevas pruebas será una acción explícita distinta. Implementación pendiente.
- Historial de trabajos consulta /api/jobs/list; comprobación actual HTTP 200 con jobs vacío. No agrega conversaciones, task-runs ni evaluaciones.
- B5-M00 es preparación parcial de lectura, no activación de la mutación.
- Misión documental final, concurrencia, recuperación, README generado con suite completa final y gate independiente: pendientes. Ningún PASS anterior sustituye estos gates.

## Publicación
No fusionar este borrador como entrega funcional. No se publica una release ni se modifica main. La sincronización del código requiere componer una candidata desde la base remota actual, preservar procedencias y superar las comprobaciones del estado final.
