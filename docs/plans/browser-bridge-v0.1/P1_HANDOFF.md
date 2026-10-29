# Traspaso P1 — Browser Bridge y ampliación versionada GEX

**Estado de entrega:** P1_MATERIALIZED · REVIEW_REQUIRED · NO FREEZE  
**Fecha:** 2026-10-29  
**Base de trabajo:** main@1ebf9b1b2c5cd75de8dd34dddb0cc581588327c4  
**PR específica:** #103 (borrador)  
**PR de arquitectura anterior:** #100 (sin fusionar)

Este traspaso es **documental/técnico**, no un handoff DONE de teamctl ni un recibo de ejecución del navegador. No activa una nueva capacidad.

## Materializado

- P1_GEX_BROWSER_PROFILE.md: decisión de extensión tipada, HUMAN/AGENT, doble autorización, único ledger, estados inciertos.
- P1_BROWSER_SCHEMA.json: cinco formas versionadas y cerradas (perfil, GEX request v2, binding, dispatch, observation). No modifica GEX_V1_SCHEMA.json.
- P1_CONTROL_MAP.json: 13 controles canónicos asociados a checks host-owned **propuestos**; NO hay checks de Browser Bridge registrados como PASS.
- P1_VECTORS.json: 26 escenarios SPEC_ONLY, incluidos host ACK sin recibo, revocación, replay, permiso ausente, conformidad que no autoriza y fallos terminales sin verificación independiente.
- tests/contracts/browser_bridge/test_p1_browser_contracts.py: pruebas de validación estructural, negativos, compatibilidad GEX v1 y oráculo de transiciones.

La Observation lleva el documento extraído como contenido inline base64 tipado (`text/plain`), limitado a 65 536 bytes decodificados, con SHA-256 y longitud. El vínculo usa request_digest, attempt_id y binding_id del Dispatch autorizado. El backend debe verificar identidad de solicitud, límite, longitud e integridad antes de crear el recibo. No se define URL, ruta ni canal de recuperación externo.

**Guardarraíles en PR:** solo se crean nuevos archivos bajo docs/plans/browser-bridge-v0.1/ y tests/contracts/browser_bridge/. No se modifican runtime, GEX, permisos, UI, CI, README, LedgerEventV1 ni el adaptador de conformidad.

## Baseline y brechas

En main, CapabilityRegistrationV1.executor_kind admite local/mcp y GEXRequestV1 requiere agent; el runtime vigente es fixture.read. Por tanto, **browser_native no se puede registrar ni ejecutar legalmente en ese perfil**. La solución P1 es una nueva forma de solicitud v2 y perfil versionado, ambos pendientes de revisión e implementación. Una acción manual utiliza initiator=HUMAN sin agent_id inventado; el backend resuelve principal y binding.

**Una sola cadena de efectos:** GEX autentica, autoriza, consume permit y persiste DISPATCH_INTENT; host/extensión ejecutan una lectura estrictamente tipada; GEX persiste ReceiptV1; verificador independiente emite VerificationResultV1. Conformidad/teamctl solo examinan la evidencia de candidata, sin autorizar operaciones.

**Chrome:** un gesto de usuario real y la vigencia comprobada de activeTab son imprescindibles, independientes del permit ADL. No tomar invocation_event_ref como prueba criptográfica de Chrome.

**Fallos:** tras DISPATCH_INTENT, si falta recibo terminal durable el resultado es UNKNOWN / RECONCILIATION_REQUIRED, no SUCCEEDED; no reintento automático.

## Verificaciones requeridas para promover P1 a ACCEPTED

Comandos que deben ejecutarse realmente sobre el mismo SHA candidato:

- python -m pytest tests/contracts/browser_bridge/test_p1_browser_contracts.py -q
- python -m pytest tests/contracts/evidence/test_domain_conformance.py -q
- python -m pytest tests/governed_execution/integration/test_fixture_slice.py tests/api/test_gex_runtime.py -q
- python -m pytest docs/governed-execution/verification/test_gex_contract_consistency.py -q
- python -m pytest tests -q
- python scripts/generate_dynamic_readme.py
- python scripts/generate_dynamic_readme.py --check --skip-tests

La generación completa de README se exige en AGENTS.md antes del cierre real. GitHub CI ejecuta pytest tests y README check, pero no sustituye por sí sola la generación de ambos README que ordena el contrato local.

Revisar externamente si el mapeo control→check constituye una comprobación semánticamente suficiente y cómo se autentica el canal host↔ADL. Los 26 vectores actuales son SPEC_ONLY, incluso si un test verifica que sus expectativas son consistentes.

## Estado de evidencia en la publicación inicial

- Inspección GitHub de GEX y adaptador F-003: **REALIZADA**, alcance estático.
- Revisión programática inicial del contrato (13 controles, 24 vectores, perfiles/versiones): **PASS_STATIC_ONLY** en la sesión de preparación, no es pytest ni test de producto. La rama correctiva añade dos vectores negativos y debe evaluarse con sus propios resultados.
- Cambios P2 de integridad de documento y separación de verificación: se someten a pytest en la rama correctiva; aún no son evidencia hasta ejecutar la suite.
- Test Python en el SHA definitivo: **PENDIENTE de resultado CI / NO DECLARADO PASS**.
- Chrome real, Windows, Native Messaging, GEX browser_native y teamctl: **NOT_RUN**.
- Revisión/aprobación humana de las extensiones versionadas: **PENDIENTE**.

## Consumidores posteriores

1. **P2 Host:** framing, pairing y transporte autenticado, sin activar ninguna capability; usar el esquema P1 solo después de revisión del contrato de MAC/nonce.
2. **P3 Extensión:** activeTab real, recurso compartido, comprobación de origen/document epoch y extracción acotada; permiso Chrome no sustituye GEX.
3. **P4 Integrador GEX:** ampliación versionada del registro, request HUMAN/AGENT, adapter nuevo bajo la única autoridad/ledger vigente; antes de editar GEX v1 abrir revisión específica y conservar fixture.read.
4. **P5/UI y P6/verificador independiente:** controlar el mismo recorrido desde chat/manual, demostrar postcondición, reconciliación y ausencia de bypass.

**Nunca** prometer que esta entrega contractual verifica el navegador o resuelve las brechas de P4. Las fases P2/P3/P4 no se marcarán READY/DONE hasta los gates de revisión, procedencia y coordinación del equipo.
