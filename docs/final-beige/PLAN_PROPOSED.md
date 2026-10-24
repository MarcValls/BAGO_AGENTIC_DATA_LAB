# Sucesor de publicación beige · PROPOSED

## Estado

Esta carpeta contiene una propuesta, sin inicializar misión, cambiar runtime, copiar producto ni publicar. PF01 RC13 permanece congelado como candidata anterior. Las preferencias finales son Configuración abajo y destacada, con acentos beige. El alcance visual RC13 no las satisface y no debe promocionarse como resultado final de esas preferencias.

## Entrada y dependencias

1. Base local P1: `165d01588bf86944d99dd5c8d9c632fa2736dc29`. La base remota y la identidad final del índice son responsabilidad de root antes de publicar.
2. Evidencia histórica PF01: `docs/verification/publication-20261024/final/handoff.json`, SHA-256 `888c17d97388243f6a62fa515a8690200eb45c15bd078f4419df65ddf06bcf7e`. Se conserva; no se modifica ni se presenta como verificación de fuentes nuevas.
3. Implementación BS01: misión `BAGO_BEIGE_SETTINGS_20261024`, freeze de tres archivos en L: App.tsx, NavigationOrder.css y navigation-control-order.test.tsx. Se revalidarán sus hashes y handoff al consumirlos. App.css histórico permanece intacto.
4. Paquete RC14: raíz aislada `C:/BAGO_TESTS/BS_20261024_RC14`. Esperar ZIP final identificado, snapshot, extracción, build y frontend tests con código de salida, observación actual y validación independiente BS03. Esta propuesta no afirma que ya existan esos resultados.

## Operación futura finita

### PFB01 · preparación

- Archivar runtime PF y registrar hashes de fuentes anteriores antes de cualquier cambio. Las evidencias PF siguen perteneciendo a RC13; crear cambio explícito con consumidores y nuevas identidades.
- Importar sólo las tres fuentes BS01 congeladas, verificando bytes. Conservar CI y once reglas `.gitattributes` ya revisadas; volver a comprobar sus hashes y efectos sin ampliarlos.
- Comparar **todas** las fuentes/frontend tests/package del snapshot RC14 contra P, detectar extras y relacionar la prueba Docker del ZIP extraído con ese conjunto exacto. No copiar builds, dependencias, ZIP, runtime ni datos.
- Incorporar manual y resumen propio en esta carpeta. Capturas nuevas RC14 seguras y sin transformación de sus bytes firmados; no usar las anteriores como actuales. No copiar logs privados sin revisión.
- Heredar las **941 PASS y1SKIP de P1** únicamente tras repetir la prueba de identidad de los233 archivos Python/requisitos/scripts e inputs README protegidos. No ejecutar otra suite Python completa automáticamente. El nuevo full de L se documenta aparte y no reemplaza el resultado de P.
- Conservar el generador, manifiesto, guía y contrato de presentación de README base; ejecutar únicamente `--check --skip-tests` en este sucesor expresamente acotado, con `PYTEST_ADDOPTS` vacío. La suite completa previa se hereda por identidad.
- Comprobar enlaces nuevos, privacidad, integridad de capturas, ámbito exacto y límites. Materializar aceptación managed y handoff inmutable.

### PFB02 · revisión independiente

Revisar pruebas y alcance después del handoff PFB01. Comprobar los hashes reales del candidato, la conservación de antecedentes, la fuente del conteo frontend, imágenes, fuente Python sin cambios y límites. No implementar las superficies revisadas. Puerta terminal sólo scoped preparation para draft PR.

## Exclusiones y límites

Sin nueva autoridad de permisos, registro dinámico ni asignaciones efectivas de herramientas. Capacidades/proveedores/WhatsApp real y CI alojada siguen **NOT_RUN** o **PROPOSED**, conforme a su evidencia. Goal Inspector pausado. No sumar pruebas heredadas, focales ni repetidas. No atribuir al puerto8093 la observación del preview: aplicación y observación real requieren registros separados.

Root conserva la autorización vigente de publicar un draft PR, sin merge, después de cerrar esta preferencia visual y los gates. Esta propuesta no realiza stage, commit, push, merge ni cambio de servicios.
