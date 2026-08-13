@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%launch_server.ps1"

if errorlevel 1 (
    echo.
    echo El servidor termino con errores.
    pause
)

endlocal
