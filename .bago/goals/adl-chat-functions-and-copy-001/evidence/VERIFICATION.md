# Evidencia de verificación

- Base de trabajo: `main`, HEAD `f94811f7b186fec36f405403230f2d48d92dfb0c`, alineada con `origin/main` al iniciar el cambio.
- Cambio funcional: `frontend/src/components/AgentChat.tsx` reconoce los ajustes de cognición/contexto y enruta la petición local a `cognition_settings`; `frontend/src/App.tsx` abre el diálogo existente en esa sección.
- Build: `npm run build` en `frontend/` — PASS (`tsc -b && vite build`, 127 módulos).
- Navegador: Playwright CLI en `http://127.0.0.1:5173/`; enviar `Abre ajustes de cognición` añadió el mensaje local y abrió Settings con el área `Cognition and context settings`. También se confirmó `Abre ajustes` → Provider & models. Consola: 0 errores y 0 warnings en la consulta de cognición.
- Contenido: `docs/agent-chat-control/TUTORIAL_PRIMER_USO.md` documenta órdenes disponibles, selección de asistente/agente, lectura limitada y propuestas. Se eliminaron explicaciones redundantes de la UI y se acortaron etiquetas/placeholders.
- README: `python scripts/generate_dynamic_readme.py --check --skip-tests` — PASS (`README verificado`; 252 casos recogidos, no ejecutados).
- Suite de tests: `NOT_RUN`; la instrucción de ejecución de tests en cierre del repositorio entra en conflicto con la directriz de mayor prioridad de no ejecutar tests salvo petición expresa.
- Sin cambios de CSS deliberados. El alcance mayor de modernización visual sigue `PREPARED` y fuera de este cambio.
