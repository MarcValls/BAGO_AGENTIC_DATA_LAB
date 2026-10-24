# Propuesta de pantalla BAGO: Entornos de desarrollo

**PROPOSED — no se ha añadido esta pantalla ni un API de control Docker.**
La entrega ejecutable actual es Compose/CLI independiente; esta propuesta sirve
para una integración posterior revisable y embebible en el chat.

```text
BAGO / Configuración / Entornos de desarrollo
┌ Motor Docker ────────────────────────────────────────────┐
│ Estado observado · fecha · versión · Linux/Windows · WSL  │
│ [Volver a comprobar]         Evidencia → diagnóstico       │
└──────────────────────────────────────────────────────────┘
┌ Candidata ────────────────────────────────────────────────┐
│ Checkout · HEAD · manifiesto SHA · diferencia de versiones │
│ [Inspeccionar contexto] [Ver exclusiones] [Ver plan]       │
└──────────────────────────────────────────────────────────┘
┌ Perfiles ─────────────────────────────────────────────────┐
│ Desarrollo React     :5173 → API existente del host        │
│ Pruebas Python/React sin sesiones ni datos activos         │
│ API aislada opcional :8089                                 │
│ Jaeger opcional      :16689 / OTLP :4329                    │
│ [Preparar] [Construir] [Arrancar selección] [Parar propios] │
└──────────────────────────────────────────────────────────┘
┌ Resultado ────────────────────────────────────────────────┐
│ Config · build · pruebas · health · UI · proveedor         │
│ Cada puerta PASS/FAIL/NOT_RUN + recibo + alcance + fecha    │
└──────────────────────────────────────────────────────────┘
```

El panel mostraría la propiedad de cada contenedor y volumen antes de actuar,
separando contenedores de este proyecto y contenedores ajenos. Una parada sólo
se aplicaría a IDs vinculados al plan revisado. No ofrecería prune ni borrado
general. Docker ausente produce una dependencia explicada, sin instalar WSL o
cambiar virtualización automáticamente.

El orquestador podría preparar un plan con revisión y argumentos explícitos;
el usuario revisaría el contexto, mounts, puertos y efectos antes de arrancarlo.
El mismo plan se ejecutaría por el CLI externo, sin depender del chat ni de un
broker nuevo. Un botón de estado nunca reemplazaría la consulta de health.

Sesión de proveedores: usar la API host existente; no pedir tokens nuevamente
ni mostrar credenciales en el panel. UI/chat y Windows/Codex/WhatsApp conservarían
sus fronteras de host. La vista no debería marcar inferencia o WhatsApp como
verificado porque Docker esté saludable.

Aceptación futura: prueba visual actual de cada acción, cancelación sin efecto,
plan obsoleto rechazado, contenedor ajeno protegido, reinicio conservando estado
honesto y evidencias vinculadas a la candidata. Capturas anonimizadas antes de
compartir. Esa aceptación futura es NOT_RUN en esta entrega.
