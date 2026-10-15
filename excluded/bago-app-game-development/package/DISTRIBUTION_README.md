# BAGO App & Game Development

Paquete instalable de Codex para orientar el desarrollo, revisión y empaquetado de aplicaciones y juegos. El ZIP de distribución agrupa todo bajo `BAGO_APP_GAME_DEVELOPMENT/` para que su extracción no mezcle los archivos fuente con el árbol de otro repositorio.

## Instalar

1. Extrae el ZIP. Se creará la carpeta `BAGO_APP_GAME_DEVELOPMENT`.
2. Abre PowerShell dentro de esa carpeta.
3. Ejecuta:

   ```powershell
   .\install.ps1
   ```

El instalador elige `$env:CODEX_HOME` o, si no está definido, `%USERPROFILE%\.codex`. Para indicar otra ruta:

```powershell
.\install.ps1 -CodexHome 'D:\Codex'
```

La skill queda en `skills\bago-app-game-development`. Si ya existe, el instalador se detiene y conserva lo que hay. No requiere Python, no instala dependencias y no activa hooks.

## Contenido

- `skills\bago-app-game-development`: skill, referencias de flujos de aplicación y juego, herramientas y verificación.
- `tools`: inventario local de proyectos, validación de hashes, instalador Python y herramientas de construcción de paquetes.
- `BAGO_BEHAVIOR_SOURCE`: archivos BAGO de referencia recopilados desde sus rutas de origen. Se agrupan aquí para consulta y trazabilidad; el instalador no los copia sobre otro repositorio ni modifica la configuración del proyecto.
- `CONTENTS_MANIFEST.json`: rutas y SHA-256 del contenido distribuido.

Los archivos fuente conservan su estructura relativa bajo `BAGO_BEHAVIOR_SOURCE/`. Las rutas de instalación de Codex se resuelven por el instalador al entorno actual, en vez de asumirse como rutas de origen.

## Herramientas del paquete

Desde esta carpeta, el inventario se puede ejecutar con:

```powershell
python .\tools\project_inventory.py --root 'RUTA\AL\PROYECTO'
python .\tools\verify_package.py .
```

El inventario es de solo lectura y ofrece señales de tecnologías detectadas; no certifica que el build o runtime funcione. La skill no concede permisos para despliegues, publicaciones, compras o cambios destructivos.
