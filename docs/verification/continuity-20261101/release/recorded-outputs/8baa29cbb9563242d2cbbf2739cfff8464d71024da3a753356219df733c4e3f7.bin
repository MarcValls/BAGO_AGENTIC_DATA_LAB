# Continuidad gobernada y Brave revision5: estado de la proyección pública

Esta entrega publica evidencia original de `CODEX_GOVERNED_CONTINUITY_20261031`, candidato `0f74f0d818f422d2a9506957e6396070300bbb77d88c602605b4fa647e7cc774`. La rama de publicación parte de `origin/main` obtenido expresamente en `ed0efc83cc39a40aac231d9aa0da77a5d30a91e7`. Es una proyección de evidencia y de la política local; no modifica el producto P1, P3 ni el binding, ni constituye una nueva ejecución de Brave.

## Resultado local comprobado

- La política de continuidad de `AGENTS.md` exige continuar etapas necesarias y autorizadas; registro y delegación no conceden permisos. Exige comprobar identidad, scopes, aprobación, STOP y revocación antes de efectos, y consumir handoffs con evidencia real.
- El hash de LOCAL_POLICY está recuperado: el `status.json` histórico vuelve a coincidir exactamente con `f5a22128f52634a073b0d92723812c4a54dfab4bb590c56cc4067f81d882b2ae`. El incidente y su recuperación se conservan como evidencia adicional; no se reemplazó silenciosamente el handoff.
- P2 revision5 pasó 69 pruebas y produjo el paquete SHA-256 `2aefdaa63fbfeadb79498acac429bee36e3fce3ac323664fa0733347a030e333`.
- Brave attempt7 realizó `connectNative` desde el popup de la extensión, handshake y preview con digest, más tres denegaciones. Runtime SHA-256 `a39a9b4d0367d03ad205b97cb78d79151a8b9db89b7b92e16aa92658a5bcfec9`. Recibo gestionado `82c2292c60ea403e9dadb313be96202d`, SHA-256 `552bb8d8f13d4a8cc31e7adcc9223c499c48c6548432412915a32288df2ccde6`.
- Limpieza verificada: entrada temporal HKCU, manifiesto, perfil aislado y procesos de host ausentes; foco del usuario conservado. Verificación SHA-256 `1bf5c6fb1386219a61f6f4ac57f18c0d974ed2589ba0b9e222ef51b1dc29a9ec`; recibo `8d3041fd47fa4d4bb821aca94f642596`, SHA-256 `75da9ac53db22df4351fc3f771acb72a5eab5007ba214432e1f804c15759fbf4`. La escritura temporal había sido autorizada por el usuario y ya se ejecutó y limpió; no sigue pendiente por permiso.
- La revisión independiente T1–T12 fue GO_SCOPED local. Dos sesiones nativas distintas continuaron mediante checkpoint/offer/accept; las canarias externas devolvieron PermissionError y conservaron SHA. La batería de gobernanza probó permisos ausentes/caducados, revocación, STOP, replay y fallos de comprobación. La revisión separada consumió un recibo real; no se contó el trabajo del autor como independiente.
- El generador README real de esta rama ejecutó 1.792 PASS, 2 SKIP y 0 FAIL/ERROR (114 subtests adicionales). La consistencia pasó en Docker y en Windows sobre el checkout final. Los logs y recibos son evidencia separada; no se vuelve a ejecutar Brave para comprobar sus hashes.

## Límites conservados

El estado nativo de `/goal` sigue pausado y no existe una herramienta de reanudación expuesta. El contrato original excluye ese estado y la configuración global de Codex. Ningún adaptador local simula `/goal resume` ni evita STOP o una decisión humana obligatoria. Los scopes de teamctl son coordinación lógica; las pruebas nativas acreditan sólo la frontera de las canarias realmente ensayadas. La terminación de descendientes Windows requirió limpieza explícita y no se afirma atomicidad universal.

El gesto de barra de herramientas y vídeo de aquel ensayo Brave R5 están NOT_RUN; se comprobó el popup y hubo un recurso fixture 404. Dos PIDs de host no tienen correlación individual por mensaje. Los intentos fallidos previos permanecen conservados. La imagen de pruebas `sha256:3d92378210d9a4b5411f2f74f9bfe08bd1f90787c5426b589e8b95486c243480` tenía pypdf 6.21.2 frente al pin 6.21.4 del candidato; esa suite no acredita el pin exacto de CI. WinRT real y CIM de Windows quedaron SKIP en Linux.

## Interpretación y comprobación pública

`PUBLICATION_INDEX.json` contiene los hashes de los objetos crudos y las rutas fuente. Ejecutar `python verify_publication.py` permite comprobar la proyección desde un clone/extracción, sin Windows ni credenciales. Se excluyen los grants de autorización, bases de control/TaskStore, lease keys, tokens, perfiles y razonamiento privado. La selección GOV es un subconjunto público: no pretende reconstruir sus 72 outputs privados. Un hash identifica los bytes; no amplía autoridad ni vuelve a probar el runtime.

Los antiguos `goal.md`, `status.json`, informes y ledgers permanecen como documentos históricos, incluidos sus estados PREPARED/PENDING/NO_GO de entonces. Este estado posterior no los reescribe. La integridad de sus handoffs se conserva. La verificación independiente de esta publicación y su disponibilidad remota se registran en los handoffs/release y el PR; publicación, verificación y aceptación tienen evidencias distintas. No se ha autorizado integrar en main.
