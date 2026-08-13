# ZAMN - launcher from the Scripts folder
# Starts the dedicated game server, web server and DuckDNS keep-alive.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $ProjectRoot "start_server.ps1"

if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf)) {
    Write-Error "No se encontró el lanzador principal: $Launcher"
    exit 1
}

Write-Host "Iniciando ZAMN desde: $ProjectRoot"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Launcher
exit $LASTEXITCODE
