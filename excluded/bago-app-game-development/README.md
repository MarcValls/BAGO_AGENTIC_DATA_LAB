# Paquete BAGO App & Game Development

Esta carpeta reúne los artefactos locales del paquete y está excluida de Git mediante `/excluded/bago-app-game-development/` en el `.gitignore` del repositorio.

## Contenido

- `BAGO_App_Game_Development_Installer_2026-10-15.zip`: distribución instalable con una sola carpeta raíz, el instalador PowerShell, el paquete y las fuentes BAGO de referencia agrupadas.
- `BAGO_archivos_comportamiento_2026-10-14.zip`: ZIP fuente de comportamiento usado para construir la distribución.
- `package/`: fuentes editables del paquete, su skill y herramientas de instalación, inventario, validación y construcción.

## Reconstruir el ZIP instalador

Desde esta carpeta, ejecuta:

```powershell
python .\package\tools\build_installer.py `
  --behavior-archive .\BAGO_archivos_comportamiento_2026-10-14.zip `
  --package-root .\package `
  --output .\BAGO_App_Game_Development_Installer_2026-10-15.zip
```

El instalador incluido se verifica extrayéndolo en una carpeta temporal y ejecutando `BAGO_APP_GAME_DEVELOPMENT\install.ps1` desde allí. La skill se copia a CODEX_HOME; las fuentes de referencia se conservan dentro del ZIP y no se aplican a otros repositorios.
