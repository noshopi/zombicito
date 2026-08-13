# duckdns auto-updater - keeps zombicito.duckdns.org pointing to this PC
$token = $env:DUCKDNS_TOKEN
$ifMissing = [string]::IsNullOrWhiteSpace($token)
if ($ifMissing) { exit 0 }
$domains = "zombicito"
$cacheFile = "$env:TEMP\duckdns_ip.txt"
$logFile = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "duckdns.log"

try { $pub = (Invoke-WebRequest -Uri "https://api.ipify.org" -TimeoutSec 10 -UseBasicParsing).Content.Trim() } catch { exit 0 }
$old = ""
if (Test-Path $cacheFile) { try { $old = (Get-Content $cacheFile -Raw).Trim() } catch {} }
if ($pub -eq $old) { exit 0 }

try {
    $resp = Invoke-WebRequest -Uri "https://www.duckdns.org/update?domains=$domains&token=$token&ip=$pub" -TimeoutSec 15 -UseBasicParsing
    $ok = ($resp.Content -eq "OK" -or $resp.StatusCode -eq 200)
    if ($ok) {
        Set-Content $cacheFile -Value $pub -NoNewline
        $msg = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $old -> $pub  OK"
        Add-Content $logFile -Value $msg
    }
} catch {}
