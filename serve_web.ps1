# ZAMN - public web page server (TcpListener, no admin needed)
# Serves the project root so the game page is visible at
#   http://zombicito.duckdns.org:7070/          (downloads page)
#   http://zombicito.duckdns.org:7070/jugar/    (play the game in the browser)
# Uses a DEDICATED port (7070 by default) on purpose: your router forwards
# port 80 to another app (juega), so ZAMN must not compete for it. Add one
# router rule: TCP 7070 -> the LAN IP of this PC.
param([int]$Port = 7070)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$mime = @{
    ".html" = "text/html; charset=utf-8"
    ".js"   = "text/javascript; charset=utf-8"
    ".css"  = "text/css; charset=utf-8"
    ".json" = "application/json"
    ".wasm" = "application/wasm"
    ".data" = "application/octet-stream"
    ".sfc"  = "application/octet-stream"
    ".png"  = "image/png"
    ".jpg"  = "image/jpeg"
    ".ico"  = "image/x-icon"
    ".exe"  = "application/octet-stream"
}

# virtual folders: URL alias -> real folder (in-browser Python game)
$virtual = @{
    "/jugar" = (Join-Path $root "webgame")
    "/play"  = (Join-Path $root "webgame")
}

$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $Port)
try { $listener.Start() }
catch { Write-Host "Could not bind port $Port (is it in use?)."; exit 1 }

# lobby directory relay: game servers POST their status, browsers GET the list
$script:Lobbies = @()

# global design gallery: players upload finished pixel-art characters
$designsDir = Join-Path $root "designs"
if (-not (Test-Path $designsDir)) { New-Item -ItemType Directory -Path $designsDir | Out-Null }

Write-Host ""
Write-Host "  ZAMN web page live at  http://zombicito.duckdns.org:$Port/" -ForegroundColor Green
Write-Host "  bound to ALL local IPs - router: forward TCP $Port to this PC's LAN IP" -ForegroundColor DarkGray
Write-Host "  game server stays on UDP 6969 - no conflict with other apps" -ForegroundColor DarkGray
Write-Host ""

while ($true) {
    $client = $null
    try { $client = $listener.AcceptTcpClient() } catch { break }
    try {
        $stream = $client.GetStream()
        $stream.ReadTimeout = 5000
        $head = ""
        $buf = New-Object byte[] 4096
        while ($head.IndexOf("`r`n`r`n") -lt 0) {
            $n = $stream.Read($buf, 0, 4096)
            if ($n -le 0) { break }
            $head += [System.Text.Encoding]::ASCII.GetString($buf, 0, $n)
        }
        $line = $head.Split("`r`n")[0]
        $parts = $line.Split(" ")
        $method = if ($parts.Count -gt 0) { $parts[0] } else { "GET" }
        $url = if ($parts.Count -gt 1) { $parts[1].Split("?")[0] } else { "/" }
        $rel = [Uri]::UnescapeDataString($url).TrimStart("/")
        $base = $root
        if ($rel -eq "") { $rel = "web/index.html" }
        foreach ($v in $virtual.Keys) {
            $a = $v.TrimStart("/")
            if ($rel -eq $a -or $rel.StartsWith($a + "/")) {
                $base = $virtual[$v]
                $rel = $rel.Substring($a.Length).TrimStart("/")
                if ($rel -eq "") { $rel = "index.html" }
                break
            }
        }
        $path = Join-Path $base $rel
        $full = [IO.Path]::GetFullPath($path)
        $ok = $full.StartsWith($base, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path $full -PathType Leaf)
        $handled = $false
        if ($url -eq "/api/announce" -and $method -eq "POST") {
            # read POST body (Content-Length)
            $cl = 0
            foreach ($hl in ($head -split "`r`n")) {
                if ($hl -like "Content-Length:*") { $cl = [int]$hl.Substring(15).Trim(); break }
            }
            while ($head.IndexOf("`r`n`r`n") -lt 0 -or ($head.Length -lt $head.IndexOf("`r`n`r`n") + 4 + $cl)) {
                $n = $stream.Read($buf, 0, 4096)
                if ($n -le 0) { break }
                $head += [System.Text.Encoding]::UTF8.GetString($buf, 0, $n)
            }
            $bi = $head.IndexOf("`r`n`r`n")
            if ($bi -ge 0) {
                $body = $head.Substring($bi + 4)
                try {
                    $o = $body | ConvertFrom-Json
                    $same = if ([string]$o.host -like "web-*") {
                        @($script:Lobbies | Where-Object { $_.host -eq $o.host })
                    } else {
                        @($script:Lobbies | Where-Object { $_.name -eq $o.name -and $_.host -eq $o.host })
                    }
                    $old = $same
                    $requests = if ($old.Count -gt 0) { @($old[0].requests) } else { @() }
                    if ([string]$o.host -like "web-*") {
                        $script:Lobbies = @($script:Lobbies | Where-Object { $_.host -ne $o.host })
                    } else {
                        $script:Lobbies = @($script:Lobbies | Where-Object { -not ($_.name -eq $o.name -and $_.host -eq $o.host) })
                    }
                    $script:Lobbies += @{ name = [string]$o.name; host = [string]$o.host; region = [int]$o.region;
                                          filled = [int]$o.filled; slots = [int]$o.slots;
                                          world = [int]$o.world;
                                          started = [int]$o.started; owner = [string]$o.owner;
                                          kinds = @($o.kinds); bots = @($o.bots); teams = @($o.teams);
                                          chars = @($o.chars); ready = @($o.ready);
                                          clients = $o.clients; requests = $requests; t = Get-Date }
                } catch {}
            }
            $bytes = [System.Text.Encoding]::UTF8.GetBytes("OK")
            $ct = "text/plain; charset=utf-8"
            $status = "200 OK"
            $handled = $true
        } elseif ($url -eq "/api/lobbies") {
            $script:Lobbies = @($script:Lobbies | Where-Object { ((Get-Date) - $_.t).TotalSeconds -lt 8 })
            $list = @($script:Lobbies | ForEach-Object {
                $details = @()
                $n = if ($_.kinds) { @($_.kinds).Count } else { 0 }
                for ($i = 0; $i -lt $n; $i++) {
                    $details += @{ slot = $i; kind = [int]$_.kinds[$i]; bot = [int]$_.bots[$i];
                                    ready = [int]$_.ready[$i]; team = [int]$_.teams[$i]; char = [int]$_.chars[$i] }
                }
                $botCount = @($details | Where-Object { $_.bot -eq 1 -and $_.kind -eq 0 }).Count
                @{ name = $_.name; host = $_.host; region = $_.region; filled = $_.filled;
                   slots = $_.slots; started = $_.started; world = $_.world;
                   bots = $botCount; free = ([int]$_.slots - [int]$_.filled - $botCount);
                   details = $details }
            })
            $json = $list | ConvertTo-Json -Compress
            if ($null -eq $json) { $json = "[]" }
            elseif ($json[0] -ne '[') { $json = "[" + $json + "]" }
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
            $ct = "application/json; charset=utf-8"
            $status = "200 OK"
            $handled = $true
        } elseif ($url -eq "/api/designs" -and $method -eq "POST") {
            # read POST body (same pattern as announce)
            $cl = 0
            foreach ($hl in ($head -split "`r`n")) {
                if ($hl -like "Content-Length:*") { $cl = [int]$hl.Substring(15).Trim(); break }
            }
            while ($head.IndexOf("`r`n`r`n") -lt 0 -or ($head.Length -lt $head.IndexOf("`r`n`r`n") + 4 + $cl)) {
                $n = $stream.Read($buf, 0, 4096)
                if ($n -le 0) { break }
                $head += [System.Text.Encoding]::UTF8.GetString($buf, 0, $n)
            }
            $bi = $head.IndexOf("`r`n`r`n")
            $ok2 = $false
            if ($bi -ge 0) {
                $body = $head.Substring($bi + 4)
                try {
                    $o = $body | ConvertFrom-Json
                    $nm = [string]$o.name
                    $nm = ($nm -replace "[^A-Za-z0-9 _\-]", "_")
                    if ($nm.Length -gt 24) { $nm = $nm.Substring(0, 24) }
                    $owner = ([string]$o.owner -replace "[^A-Za-z0-9_-]", "_")
                    if ($owner.Length -gt 32) { $owner = $owner.Substring(0, 32) }
                    if ($owner.Trim() -eq "") { $owner = "anonymous" }
                    $prefix = if ([bool]$o.public) { "public" } else { $owner }
                    if ($nm.Trim() -ne "" -and -not [string]::IsNullOrEmpty([string]$o.png)) {
                        Get-ChildItem -Path $designsDir -Filter ("{0}__{1}__*.png" -f $prefix, $nm) -ErrorAction SilentlyContinue | Remove-Item -Force
                        $f = Join-Path $designsDir ("{0}__{1}__{2}.png" -f $prefix, $nm, [DateTime]::Now.Ticks)
                        [IO.File]::WriteAllBytes($f, [Convert]::FromBase64String([string]$o.png))
                        $ok2 = $true
                    }
                } catch {}
            }
            $bytes = [System.Text.Encoding]::UTF8.GetBytes('{"ok":' + ($ok2.ToString().ToLower()) + '}')
            $ct = "application/json; charset=utf-8"
            $status = "200 OK"
            $handled = $true
        } elseif ($url -eq "/api/lobbies/action" -and $method -eq "POST") {
            $cl = 0
            foreach ($hl in ($head -split "`r`n")) {
                if ($hl -like "Content-Length:*") { $cl = [int]$hl.Substring(15).Trim(); break }
            }
            while ($head.IndexOf("`r`n`r`n") -lt 0 -or ($head.Length -lt $head.IndexOf("`r`n`r`n") + 4 + $cl)) {
                $n = $stream.Read($buf, 0, 4096)
                if ($n -le 0) { break }
                $head += [System.Text.Encoding]::UTF8.GetString($buf, 0, $n)
            }
            $ok2 = $false
            try {
                $bi = $head.IndexOf("`r`n`r`n")
                $o = ($head.Substring($bi + 4) | ConvertFrom-Json)
                $l = @($script:Lobbies | Where-Object { $_.host -eq [string]$o.host })[0]
                if ($null -ne $l -and [string]$o.client -ne "") {
                    if ($null -eq $l.requests) { $l.requests = @() }
                    $l.requests += @{ client = [string]$o.client; action = [string]$o.action;
                                      slot = [int]$o.slot; ready = [int]$o.ready }
                    $l.t = Get-Date
                    $ok2 = $true
                }
            } catch {}
            $bytes = [System.Text.Encoding]::UTF8.GetBytes('{"ok":' + ($ok2.ToString().ToLower()) + '}')
            $ct = "application/json; charset=utf-8"; $status = "200 OK"; $handled = $true
        } elseif ($url -like "/api/lobbies/state/*") {
            $hostId = [Uri]::UnescapeDataString($url.Substring("/api/lobbies/state/".Length))
            $l = @($script:Lobbies | Where-Object { $_.host -eq $hostId })[0]
            if ($null -ne $l) {
                $json = $l | ConvertTo-Json -Compress -Depth 6
                $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
                $ct = "application/json; charset=utf-8"; $status = "200 OK"
            } else {
                $bytes = [System.Text.Encoding]::UTF8.GetBytes('{"error":"not found"}')
                $ct = "application/json; charset=utf-8"; $status = "404 Not Found"
            }
            $handled = $true
        } elseif ($url -eq "/api/designs/publish" -and $method -eq "POST") {
            $cl = 0
            foreach ($hl in ($head -split "`r`n")) {
                if ($hl -like "Content-Length:*") { $cl = [int]$hl.Substring(15).Trim(); break }
            }
            while ($head.IndexOf("`r`n`r`n") -lt 0 -or ($head.Length -lt $head.IndexOf("`r`n`r`n") + 4 + $cl)) {
                $n = $stream.Read($buf, 0, 4096)
                if ($n -le 0) { break }
                $head += [System.Text.Encoding]::UTF8.GetString($buf, 0, $n)
            }
            $ok2 = $false
            try {
                $bi = $head.IndexOf("`r`n`r`n")
                $o = ($head.Substring($bi + 4) | ConvertFrom-Json)
                $owner = ([string]$o.owner -replace "[^A-Za-z0-9_-]", "_")
                $id = [IO.Path]::GetFileName([string]$o.id)
                $source = Join-Path $designsDir $id
                if ($owner -and $id.StartsWith($owner + "__") -and (Test-Path $source -PathType Leaf)) {
                    $parts = ([IO.Path]::GetFileNameWithoutExtension($id) -split "__", 3)
                    if ($parts.Count -ge 3) {
                        $target = Join-Path $designsDir ("public__{0}__{1}.png" -f $parts[1], $parts[2])
                        Move-Item -LiteralPath $source -Destination $target -Force
                        $ok2 = $true
                    }
                }
            } catch {}
            $bytes = [System.Text.Encoding]::UTF8.GetBytes('{"ok":' + ($ok2.ToString().ToLower()) + '}')
            $ct = "application/json; charset=utf-8"
            $status = "200 OK"
            $handled = $true
        } elseif ($url -eq "/api/designs/mine" -or $url -like "/api/designs/mine/*") {
            $owner = [Uri]::UnescapeDataString($url.Substring("/api/designs/mine/".Length)) -replace "[^A-Za-z0-9_-]", "_"
            $list = @(Get-ChildItem -Path $designsDir -Filter ("{0}__*.png" -f $owner) -ErrorAction SilentlyContinue | ForEach-Object {
                $parts = $_.BaseName -split "__", 3
                @{ id = $_.Name; name = if ($parts.Count -ge 2) { $parts[1] } else { $_.BaseName }; bytes = $_.Length;
                   date = $_.LastWriteTime.ToString("dd/MM HH:mm") }
            })
            $json = $list | ConvertTo-Json -Compress
            if ($null -eq $json) { $json = "[]" }
            elseif ($json[0] -ne '[') { $json = "[" + $json + "]" }
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
            $ct = "application/json; charset=utf-8"; $status = "200 OK"; $handled = $true
        } elseif ($url -eq "/api/designs") {
            $list = @(Get-ChildItem -Path $designsDir -Filter "public__*.png" -ErrorAction SilentlyContinue | ForEach-Object {
                $parts = $_.BaseName -split "__", 3
                @{ id = $_.Name; name = if ($parts.Count -ge 2) { $parts[1] } else { $_.BaseName }; bytes = $_.Length;
                   date = $_.LastWriteTime.ToString("dd/MM HH:mm") }
            })
            $json = $list | ConvertTo-Json -Compress
            if ($null -eq $json) { $json = "[]" }
            elseif ($json[0] -ne '[') { $json = "[" + $json + "]" }
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
            $ct = "application/json; charset=utf-8"
            $status = "200 OK"
            $handled = $true
        } elseif ($url -like "/api/designs/*") {
            $f = Join-Path $designsDir ([IO.Path]::GetFileName([Uri]::UnescapeDataString($url.Substring("/api/designs/".Length))))
            $full2 = [IO.Path]::GetFullPath($f)
            if ($full2.StartsWith($designsDir, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path $full2 -PathType Leaf)) {
                $bytes = [IO.File]::ReadAllBytes($full2)
                $ct = "image/png"
                $status = "200 OK"
            } else {
                $bytes = [System.Text.Encoding]::UTF8.GetBytes("not found")
                $ct = "text/plain; charset=utf-8"
                $status = "404 Not Found"
            }
            $handled = $true
        }
        if (-not $handled) {
            if ($ok) {
                $bytes = [IO.File]::ReadAllBytes($full)
                $ext = [IO.Path]::GetExtension($full).ToLower()
                if ($mime.ContainsKey($ext)) { $ct = $mime[$ext] } else { $ct = "application/octet-stream" }
                $status = "200 OK"
            } else {
                $bytes = [System.Text.Encoding]::UTF8.GetBytes("<html><body><h1>404 Not Found</h1></body></html>")
                $ct = "text/html; charset=utf-8"
                $status = "404 Not Found"
            }
        }
        $resp = "HTTP/1.1 $status`r`nContent-Type: $ct`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-store`r`nPragma: no-cache`r`nConnection: close`r`n`r`n"
        Write-Host ("[REQ] " + $method + " " + $url + " -> " + $status + " " + $bytes.Length)
        $respBytes = [System.Text.Encoding]::ASCII.GetBytes($resp)
        $stream.Write($respBytes, 0, $respBytes.Length)
        if ($method -ne "HEAD") { $stream.Write($bytes, 0, $bytes.Length) }
        $stream.Flush()
    } catch {
        Add-Content -Path (Join-Path $root "server_err.log") -Value ("[ERR " + (Get-Date) + "] " + $_.Exception.ToString() + " URL=" + $url)
    }
    if ($client) { try { $client.Close() } catch {} }
}
