# Evidencia de verificación

- Base de trabajo: rama `main`, HEAD `f94811f7b186fec36f405403230f2d48d92dfb0c`. Se preservó el worktree sucio preexistente; no hay commit de estos cambios.
- Baseline de cambio: `adl-nav-followup-20261018-a`, SHA-256 `7728526adada5a530c15b1f7971e437a95aebff86be957da4449f8de726fc77b`, guardado fuera del repositorio bajo `%TEMP%`.
- La UI no decide destinos con frases o expresiones regulares. El control modela `navigate`, `answer` y `clarify`; solo una navegación con destino registrado cambia la vista. El destino sigue validado contra `CONTROL_NAVIGATION_VIEWS`.
- La lectura de archivos continúa acotada y el tool de navegación solo se ofrece al chat de control. El helper no lo ofrece por defecto a chats de agente.
- Normalización fail-closed: destino desconocido o salida estructurada sin decisión válida responde en chat; no navega.
- Ollama local 0.40.4 + `llama3.2:3b`, mediante `control_chat` y el adaptador local: 5/5 casos observados. Razonamiento -> `cognition_settings`; trabajos -> `jobs`; pasos de ejecución -> `traces`; proveedor/modelo -> `provider_settings`; pregunta explicativa sobre Evaluation -> `operation=chat`. La clasificación del chat de control usa temperatura 0. El servicio solo se contactó por `127.0.0.1`; no hubo llamadas cloud.
- La prueba de inferencia ejecutó el handler y adaptador reales en proceso, con configuración local sustituida solo durante el harness y base temporal. No levantó HTTP, navegador ni frontend vivo.
- `python -m pytest tests/test_semantic_navigation.py -q` - PASS, 8 pruebas.
- Pruebas afectadas por el cambio de contrato - PASS, 14 pruebas combinadas tras actualizar dobles de `chat_turn` y el retorno del tool-loop.
- `python -m py_compile src/api/server.py src/providers/ollama.py` - PASS.
- `npm run build` en `frontend/` - PASS (`tsc -b && vite build`, 127 módulos); no se editaron archivos de interfaz en esta tarea.
- `python scripts/generate_dynamic_readme.py` - primer intento FAIL en estado intermedio: 255 pasaron y 5 fallaron porque las pruebas aún simulaban el contrato anterior. Se actualizaron los dobles de `chat_turn` y el retorno de cuatro valores; repetición final PASS: 260 tests.
- `python scripts/generate_dynamic_readme.py --check --skip-tests` - PASS (`README verificado`; 260 casos recogidos, suite no repetida en este comando).
- `python .bago/bin/bago.py status` - intento fallido: este checkout no contiene `.bago/bin/bago.py`; se usó el contexto local disponible.
- Navegador/flujo visual - NOT_RUN. No hubo cambios de CSS, layout o estructura visual.

