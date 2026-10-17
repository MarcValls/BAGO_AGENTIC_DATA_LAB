# Validación live externa — 2026-10-17

## Resultado

| Proveedor | Resultado | Alcance ejecutado |
|---|---|---|
| Ollama Cloud | PASS | Catálogo `/api/tags` consultado; 21 modelos listados. Una inferencia con `gemma4:31b`, prompt fijo no sensible, y salida coincidente exactamente con `BAGO OLLAMA LIVE PASS` (2,53 s; 21 caracteres). |
| AWS Free Tier | BLOCKED | La lectura de identidad/cobertura falló al resolver credenciales (`NoCredentialsError`). Cost Explorer quedó sin consultar. |
| AWS Bedrock | BLOCKED antes de la invocación | El preflight STS no encontró credenciales; la ruta confirmó que no intentó Converse. No se consumió inferencia Bedrock. |
| OpenMetadata | NOT RUN: servicio no disponible | No había URL externa configurada. El healthcheck local en `localhost:8586` rechazó la conexión; el validador terminó en 2 s, antes de login o creación de entidades. No quedaron recursos que limpiar. |
| commercetools | NOT RUN | El código del escenario L9 indica expresamente que genera evidencia de portfolio y no contacta la API comercial. No se detectó una ruta live habilitada para llamar con configuración disponible. |

## Límites y costes

- La llamada de Ollama Cloud fue autorizada explícitamente por el usuario y consistió en una única inferencia de control. El proveedor no expuso aquí el coste de esta solicitud; no se afirma coste cero.
- AWS recibió intentos de resolución local de credenciales, pero ninguna petición autenticada a STS/Bedrock llegó a ejecutarse. No se hizo una llamada facturable a Bedrock.
- OpenMetadata solo recibió un GET local al healthcheck. No se usó un servicio remoto ni se hicieron mutaciones.
- No se imprimieron ni guardaron claves, tokens ni contraseñas.

## Reproducibilidad

- Repositorio: `BAGO5_ADL`; HEAD observado: `c7b8e2ded64d7f004e82a3a8bfd7891ce9b39490`.
- Ollama: `src/providers/ollama.py` (`discover_models`, `chat`).
- AWS: `scripts/run_l6_aws_live_validation.py` y `scripts/run_l6_aws_free_tier_validation.py`, evidencia desactivada para no sobrescribir registros previos.
- OpenMetadata: `scripts/run_l8_openmetadata_live_validation.py`, timeout de healthcheck reducido a 2 s y evidencia desactivada.
- La advertencia de compatibilidad Pydantic con Python 3.14 apareció durante importación; no impidió la llamada Ollama.

## Cierre de repositorio

- `python scripts/generate_dynamic_readme.py`: PASS; suite completa, 250 tests pasados.
- `python scripts/generate_dynamic_readme.py --check --skip-tests`: PASS; README verificado, suite no repetida en esta comprobación.


## Reintento exhaustivo — continuación autorizada

### AWS: perfil y autenticación

- Se localizó `bago-free` en `~/.aws/config`; no hay `~/.aws/credentials`, variables AWS, configuración SSO completa ni archivos de caché SSO. La sección solo contiene `login_session`.
- `GetCallerIdentity` con ese perfil falló con `LoginRefreshRequired`; la salida raw se suprimió.
- `aws sso login --profile bago-free` no puede iniciar: faltan `sso_start_url` y `sso_region`.
- `aws login --profile bago-free` se intentó primero sin región y sin consola Windows; devolvió esos requisitos. Con `AWS_REGION=us-east-1` temporal y consola TTY, abrió el flujo oficial de login de AWS en el navegador local. La CLI sigue esperando el callback; el enlace/estado de autorización no se registra. Bedrock/Free Tier solo podrán probarse después de que la CLI obtenga identidad.
- No apareció ninguna credencial AWS en Windows Credential Manager por nombre de destino. No se leyó ni imprimió ningún valor secreto.

### OpenMetadata: prueba local real

- El primer arranque encontró el directorio persistente existente `infra/openmetadata/docker-volume/db-data` en estado InnoDB inconsistente (tablespaces `.ibd` ausentes y crash de MySQL); el contenedor quedó unhealthy. El directorio se dejó intacto a nivel de borrado y no se volvió a montar.
- Para proseguir sin tocar esos datos, se arrancó el stack con un bind mount temporal aislado para MySQL. La validación real terminó **PASS** en los ocho checks: salud, JWT, búsqueda, linaje, ownership JSON Patch, schema JSON Patch, definición de calidad y denegación pre-transporte. Siete recibos; `cleanup_status=PASS`.
- Se detuvieron los contenedores del stack iniciado y se retiraron el directorio temporal y su override. Los volúmenes nombrados del proyecto se preservaron. El Jaeger previo (`bago-otel-jaeger-1`) quedó intacto.

### commercetools

- No hay variables `CTP_*`/`COMMERCETOOLS_*`, archivos `.env` aplicables, configuración de proveedor, ni destino con nombre commercetools en Windows Credential Manager.
- El código solo contiene el escenario offline de portfolio; no hay cliente OAuth/API ni endpoint live al que dirigir una llamada autenticada. No se inventó un proyecto/tenant ni se enviaron solicitudes anónimas que no validarían el comportamiento de la integración.


### Cierre de esta continuación

- `aws login` permaneció esperando una autenticación/callback del navegador y se canceló después de no recibirlo. No se emitieron credenciales, no se consultó STS con una sesión válida y no se llamó a Bedrock.
- `python scripts/generate_dynamic_readme.py`: PASS, suite completa con 250 tests pasados.
- `python scripts/generate_dynamic_readme.py --check --skip-tests`: PASS, README verificado.
- Riesgo observado: el intento inicial de arrancar OpenMetadata usó el bind mount persistente preexistente antes de detectar su corrupción. MySQL registró tablespaces faltantes/crash y actualizó/creó algunos artefactos internos de recuperación en ese directorio. No se borraron archivos ni se intentó repararlo; el stack se apagó y la validación PASS posterior usó almacenamiento temporal aislado. El directorio persistente requiere revisión/restauración independiente antes de reutilizarlo.


## AWS tras login completado por el usuario

- El callback de `aws login` se completó en el navegador y el perfil `bago-free` quedó autenticado. STS confirmó identidad de tipo `root` (cuenta enmascarada `6100…13`).
- AWS Free Tier API: **PASS**; plan `FREE / ACTIVE`, USD 100.00 de créditos restantes, 0 filas de uso. `zero_billing_status=NOT_PROVEN`.
- Bedrock Converse `amazon.nova-lite-v1:0`: **FAIL/ThrottlingException**, límite diario de tokens agotado; reintentos desactivados; 0 tokens reportados.
- Tras consultar el catálogo on-demand, una única llamada alternativa a `amazon.nova-micro-v1:0` devolvió el mismo throttling; 0 tokens reportados. No se hicieron más intentos para evitar llamadas repetidas inútiles.
- No hubo respuesta generada ni éxito de inferencia; el error fue cuota del servicio, no autenticación. La interfaz propuesta permitirá completar login y comprobar identidad, y expondrá errores de cuota cuando se haga una inferencia desde la ruta de ejecución correspondiente.
