# Contrato de integración — 2026-10-23

Objetivo: integrar las cinco candidatas conservando sus cambios, validar el conjunto
y resolver la recarga Docker. No equivale a copiar un frontend completo.

## Entradas y autoridad
INPUTS.json fija base remota recién obtenida, fuentes actuales y SHA-256.
Las evidencias previas son históricas. Las fuentes originales y el principal
permanecen intactos; los cambios nuevos se realizan en esta candidata.
No hay runtime .bago/bin/bago.py en esta base: usar teamctl canónico real.

## Superficies que deben conservarse
- Agentes agrupados: gestión, creación, pruebas, evaluación; edición Sin asignar,
  revisión accesible y recuperación Windows antes de borrar perfiles de prueba.
- Papelera: confirmación de eliminación permanente, revisión, aislamiento de proyecto.
- Comunicaciones: mismo borrador/ID en chat y pantalla, programación persistente,
  validación de adjuntos y ausencia de reintento de envíos inciertos.
- WhatsApp: pantalla Settings, sesión propia por QR, selección CDP segura, estados
  honestos y persistencia. Ningún nuevo mensaje real sin autorización concreta.
- Contactos: CRUD local y Google selectivo; no confundir configuración con conexión
  real. Conservar núcleo CLI/SDK externo y su contrato; Google vivo depende de
  configuración/consentimiento externos. Comprobar uso de contactos desde Comunicaciones.
- Workspace: misma pantalla/tarjeta chat, propuesta sin efectos automáticos,
  contexto/estado/continuidad reales al vincular; archivos/papelera/Git con revisiones.
- Misma sesión/canal host de proveedores; no copiar tokens ni sobreescribir config
  Ollama privada del principal. Una preview aislada sin proveedor no exige re-registro.

## Acoplamiento frontend/backend congelado para la primera composición
Conservar rutas y DTO de cada candidata. Decisiones chat: communication_draft y
workspace_action, referencias persistidas coexistentes; ninguna mutación por la
mera respuesta del modelo. La interfaz presenta controles explícitos de revisión.
App/AgentChat/server se fusionan por hunks contra base común. El dueño backend
documenta cualquier incompatibilidad antes de cambiar contratos consumidos por UI.
README sólo desde sus entradas canónicas, conservando capas de todas las candidatas.

## Docker y aceptación
Conservar guardas de identidad/archivos extra, proyecto explícito, puertos locales,
parada disponible con evidencia STALE y volúmenes separados. Diagnosticar causa
real; demostrar alta/edición/eliminación de archivo público y HMR React existente
y nuevo sin reiniciar contenedor/proceso. Root observa DOM en Brave existente.
Después comprobar el mismo recorrido sobre la fuente integrada identificada.

## Puertas finales
Regresiones combinadas; pruebas cruzadas de chat/pantallas/persistencia; uso externo
de SDKs; reproducción visual y capturas actuales seguras; Docker real; generador
README completo y check; preservación de originales; revisión independiente.
No sumar pruebas repetidas. No promocionar mientras falte un requisito obligatorio.
Las fases de construcción entregan snapshots/patches inmutables como handoff;
son evidencias iniciales, no validación final de los bytes que después se reparen.
Toda reparación de composición registra causa/diff y pruebas nuevas en I05.
Cambios de contratos requieren CR con afectados y fingerprint, no edición silenciosa.
