# Usar la sesión actual de Codex en ADL

Solicitud: reutilizar la cuenta ChatGPT que ya está iniciada en Codex, igual
que la extensión del IDE. No pedir API key ni crear otro registro de cuenta.

Baseline: HEAD `76e57ca7dd5f26fd27a40d81324d945ec798c867`, árbol con cambios
previos conservados. El candidato anterior está identificado por el manifiesto
`../ADL-LIVE-INFERENCE-GPT-COPILOT-001/evidence/candidate.json`.

Hecho de entrada: CLI instalado 0.163.0. `codex login status` en contexto del
usuario devuelve `Logged in using ChatGPT`; el proceso aislado no ve esa sesión.
No se leen ni copian tokens: Codex conserva la autenticación.

## Plan y aceptación

1. Consultar cuenta y modelos mediante el app-server oficial, con protocolo
   exportado por el CLI instalado. Detectar la sesión existente en Configuración.
2. Ofrecer «Usar mi sesión de Codex en ADL», sin campo de credenciales, y elegir
   un modelo del catálogo. Guardar solo preferencias de proveedor/modelo.
3. Enrutar el chat principal, borradores y perfiles/Runner a la opción explícita;
   permitir volver a Ollama. Conservar perfiles antiguos y otros proveedores.
4. Mantener las operaciones materiales en el límite BER. Codex produce texto
   o propuestas estructuradas en un directorio temporal, con herramientas
   nativas, conectores, hooks, búsqueda y delegación deshabilitados.
5. Probar sesiones ausentes, errores y propuestas no autorizadas con transporte
   simulado; ejecutar una comprobación breve de inferencia con la sesión real
   solicitada, sin enviar archivos del proyecto.
6. Compilar, ejecutar regresiones y el generador/check de README. Recargar solo
   el servidor de este repositorio y comprobar la API y el build servido.

Recorrido: Settings → Proveedores y modelos → OpenAI Codex → detectar sesión →
elegir modelo → Usar mi sesión → chat de ADL. La cuenta y la inferencia son estados
distintos: una sesión detectada no equivale por sí sola a una respuesta en vivo.

Estado de entrada: `PROPOSED`. Evidencia final y límites en `evidence/`.
