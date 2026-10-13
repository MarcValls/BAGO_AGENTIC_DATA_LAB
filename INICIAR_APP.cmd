@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-local-ui.ps1"
if errorlevel 1 pause
endlocal
