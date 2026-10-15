# BAGO App & Game Development package

Paquete instalable para orientar trabajo de Codex en aplicaciones y juegos. Combina el contexto BAGO seleccionado, una skill adaptable por tarea, referencias especializadas y utilidades locales de inspección y empaquetado.

## Contenido

- `skills/bago-app-game-development/`: skill Codex y referencias de entrega.
- `tools/project_inventory.py`: inventario local de stacks de aplicación y motores/frameworks de juegos. Solo lectura; no instala ni modifica el proyecto inspeccionado.
- `tools/refresh_manifest.py`: regenera o comprueba el manifiesto SHA-256 del paquete.
- `tools/verify_package.py`: valida hashes, archivos y enlaces internos del paquete.
- `tools/install_skill.py`: instala la skill en el directorio de skills de Codex sin sobrescribir una instalación existente.
- `tools/build_distribution.py`: integra este paquete en el ZIP BAGO existente, conservando sus rutas y generando un manifiesto SHA-256.
- `tools/build_installer.py`: construye la distribución instalable con directorio raíz único y fuentes BAGO agrupadas.
- `manifest.json`: inventario y hashes del paquete.

## Instalar la skill

Desde PowerShell, con el paquete extraído en el directorio actual, instala la skill en una ruta que Codex descubre:

```powershell
python .\tools\install_skill.py
```

El instalador usa `$env:CODEX_HOME` si está definido; si no, usa `$env:USERPROFILE\.codex`. Copia la skill a `skills\bago-app-game-development`. Si ya existe, se detiene sin sobrescribirla. Para elegir otra raíz de Codex, pasa `--codex-home "RUTA"`.

Después invócala con `$bago-app-game-development` o deja que Codex la seleccione según la tarea. Las referencias son relativas a `SKILL.md`; conserva la carpeta completa.

## Usar el inventario de proyecto

```powershell
python .\tools\project_inventory.py --root "RUTA\AL\PROYECTO"
```

La salida es JSON con marcadores y frameworks reconocidos. Es una pista de descubrimiento, no una certificación del build, del runtime ni de la configuración completa.

## Validar o reconstruir el ZIP

```powershell
python .\tools\refresh_manifest.py .
python .\tools\verify_package.py .
```

El constructor conserva las entradas originales y las rutas del primer ZIP, reemplaza de forma determinista solo su propio prefijo de paquete y añade `BAGO_PACKAGE_MANIFEST.json`. Revisa el manifiesto antes de instalar. No registra plugins, instala dependencias ni activa hooks.

## Límites

La skill guía el trabajo; no concede permisos de despliegue, publicación, compra de activos, acceso a servicios ni cambios destructivos. Las capacidades de Codex, motores, SDKs y conectores se comprueban en el entorno actual. El inventario no lee valores de secretos ni escribe en el proyecto explorado.
