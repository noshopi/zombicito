# ZAMN - dedicated server launcher + DuckDNS keep-alive
# ======================================================
# Keeps zombicito.duckdns.org pointed at THIS PC and runs the game server
# on UDP port 6969, plus the web page on TCP 7070. Required router rules
# (they don't clash with your other apps - each one has its own port):
#   UDP 6969  -> the LAN IP of this PC   (game server)
#   TCP 7070  -> the LAN IP of this PC   (web page: http://zombicito.duckdns.org:7070/)
# The game auto-connects to zombicito.duckdns.org when it opens.

$ErrorActionPreference = "Continue"

$Token   = $env:DUCKDNS_TOKEN
$Domains = "zombicito"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Server  = Join-Path $ScriptRoot "zamn.py"

function Update-DuckDns {
    if ([string]::IsNullOrWhiteSpace($Token)) {
        Write-Host "[DuckDNS] DUCKDNS_TOKEN is not configured. Skipping update."
        return $false
    }
    try {
        $r = Invoke-RestMethod -Uri "https://www.duckdns.org/update?domains=$Domains&token=$Token&ip=" -TimeoutSec 20
        Write-Host ("[DuckDNS] " + $r)
        return ($r -eq "OK")
    } catch {
        Write-Host ("[DuckDNS] update failed: " + $_.Exception.Message)
        return $false
    }
}

if (-not (Test-Path $Server)) { Write-Host "Missing $Server - run this from the project root."; exit 1 }

# open the ports in Windows Firewall when running elevated
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
    netsh advfirewall firewall add rule name="ZAMN Game 6969 UDP" dir=in action=allow protocol=UDP localport=6969 | Out-Null
    netsh advfirewall firewall add rule name="ZAMN Web 7070" dir=in action=allow protocol=TCP localport=7070 | Out-Null
    Write-Host " Firewall: rules for UDP 6969 + TCP 7070 added."
} else {
    Write-Host " Not elevated - skip firewall rules. If the page is unreachable from outside,"
    Write-Host " run this script AS ADMINISTRATOR once (or allow powershell in Windows Firewall)."
}

Write-Host "============================================="
Write-Host " ZAMN dedicated server"
Write-Host " game: zombicito.duckdns.org:6969 (UDP)"
Write-Host " page: http://zombicito.duckdns.org:7070/"
Write-Host "============================================="
if (Update-DuckDns) { Write-Host " Public IP registered - domain is live." }
else { Write-Host " WARNING: DuckDNS update failed." }

$srv = Start-Process -FilePath "python" -ArgumentList "-u",$Server,"--server" -NoNewWindow -PassThru
Write-Host (" Server PID " + $srv.Id + " running. Close this window to stop it.")

$webLog = Join-Path $PSScriptRoot "web_server.log"
$webErrLog = Join-Path $PSScriptRoot "web_server_err.log"
$web = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File",(Join-Path $PSScriptRoot "serve_web.ps1"),"-Port","7070" -WindowStyle Hidden -RedirectStandardOutput $webLog -RedirectStandardError $webErrLog -PassThru
Write-Host (" Web page server PID " + $web.Id + " on port 7070 (logs: web_server.log, web_server_err.log)")

while (-not $srv.HasExited) {
    Start-Sleep -Seconds 300
    Update-DuckDns | Out-Null
}
Write-Host "Server exited."
