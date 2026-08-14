# ZAMN server watchdog: keeps serve_web.ps1 alive, restarting it if it ever exits.
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $root "server_guard.log"
$last = Get-Date
while ($true) {
    $p = Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $root 'serve_web.ps1') -RedirectStandardOutput (Join-Path $root 'server_stdout.log') -RedirectStandardError (Join-Path $root 'server_stderr.log') -PassThru
    $p.WaitForExit()
    $now = Get-Date
    $up = [Math]::Round(($now - $last).TotalSeconds)
    try {
        Add-Content -Path $log -Value ("[RESTART " + $now.ToString("dd/MM HH:mm:ss") + "] servidor murio tras " + $up + "s, relanzando")
    } catch {}
    $last = $now
    Start-Sleep -Seconds 2
}