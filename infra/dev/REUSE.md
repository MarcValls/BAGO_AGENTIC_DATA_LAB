# Reuso funcional y fronteras

Se inspeccionaron nueve entradas actuales ADL y los árboles completos, sin
truncar, de MarcValls/BAGO f3804a7e9333607561d28fd5075569e725aa0bb0 y
MarcValls/BAGO5_LAYERS aa383c8266935c2f346a1464ad3200f055731c16. En esos dos
árboles no se encontraron Dockerfile/.dockerignore/Compose. El inventario y
hashes de los archivos ADL están en evidence/attempt01/reuse-diagnostics.json.

| Entrada existente | Hallazgo | Reuso en esta candidata |
|---|---|---|
| Dockerfile.ui | Multi-stage Python3.11 y Node22; runtime container ya existente | Mismos stacks y servidor, separados en imágenes dev/test; sin duplicar backend |
| frontend/vite.config.ts | BAGO_API_PROXY_TARGET ya existe | Se usa tal cual, apuntando al host con host.docker.internal |
| requirements-test.txt | Dependencias API de pruebas y Pillow13.0.0 declaradas | Se instala su contrato completo en la imagen Python |
| CI | Instala ffmpeg antes de pytest y usa Python3.11 | Se lleva ese orden a la imagen Linux |
| compose.yaml/frontend Dockerfile | Plantilla3000 usa npm start, inexistente en package.json actual | No se adopta esa entrada; Vite usa npm run dev en5173 |
| compose.debug.yaml | Arranca index.js ajeno a la entrada Vite | Se conserva original y no se usa |
| docker-compose.ui.yml | Monta .bago y agentes RW del checkout activo | Se evita importar ese estado; volúmenes nuevos y código seleccionado RO |
| observability compose | Jaeger con puertos genéricos y exposición amplia | Servicio opt-in con imagen local identificada y puertos propios loopback |

La inspección estática detecta desacuerdos de entradas; no se ejecutaron ni se
reescribieron las configuraciones antiguas para atribuirles fallos nuevos.
No se tocaron sus contenedores ni las instalaciones de usuario.

Se detuvieron dos exportaciones propias antes de hacer build porque incluían
documentación histórica/builds. Se conservaron como intentos interrumpidos fuera
del contexto final. La allowlist final contiene355archivos y el contexto de build
sólo admite context-public/docker; no incorpora esas copias. El empaquetado final
también las excluye. Estos intentos no son evidencia de compilación.

La primera ejecución construyó ambas imágenes y pasó el smoke Python, pero la
colección focal falló al importar la API: faltaba su esquema público GEX.
evidence/attempt01 conserva logs/ejecuciones/manifiesto originales. Se añadió
exclusivamente docs/governed-execution/GEX_V1_SCHEMA.json a la allowlist; la
exportación final registra su hash y el hash del manifiesto previo. Esto evita
reintroducir archivos históricos para satisfacer una dependencia de runtime.

La segunda ejecución pasó13pruebas Python, pero el build React detectó que el
filtro genérico evidence había excluido EvidenceExplorer.tsx/css. Se preservó
evidence/attempt02 y se admitieron esos dos archivos públicos exactos en el
exportador y .dockerignore. No se admiten por ello logs/recibos ni carpetas
arbitrarias de evidencia. La tercera ejecución usa el manifiesto355final.

## Resultado final y conservación

Los intentos 03–06 conservan omisiones de exportación/contexto, el fallo de
Jaeger API antigua y el error de clasificación de contenedores propios.
El recibo final ejecutó 14 comandos y cuatro sondas HTTP con PASS.
Las guardas finales cubren identidad, archivos extra, parada con fuente editada,
proyecto explícito y puertos numéricos. La edición de activos existentes pasó,
pero archivos nuevos no se sirvieron pese a existir en FS y observar READY antes
de mutar. Se conserva FAIL, sin integrar wrappers experimentales ni promover HMR.
