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
$script:Lobbies = @{}   # keyed: web -> "web-<userId>", native -> "host|name"

# global design gallery: players upload finished pixel-art characters
$designsDir = Join-Path $root "designs"
if (-not (Test-Path $designsDir)) { New-Item -ItemType Directory -Path $designsDir | Out-Null }
$usersFile = Join-Path $root "auth_users.json"
$script:Users = @{}
$script:Sessions = @{}
$script:Players = @{}   # userId -> {email, num, lobby, lastSeen}
if (Test-Path $usersFile) {
    try {
        $savedUsers = Get-Content -LiteralPath $usersFile -Raw | ConvertFrom-Json
        foreach ($p in $savedUsers.psobject.Properties) { $script:Users[$p.Name] = $p.Value }
        $nextNum = 1
        foreach ($email in @($script:Users.Keys)) {
            if ($null -eq $script:Users[$email].num) {
                $script:Users[$email].num = $nextNum
            }
            if ($script:Users[$email].num -ge $nextNum) { $nextNum = [int]$script:Users[$email].num + 1 }
        }
        Save-AuthUsers
    } catch {}
}

function Save-AuthUsers {
    $script:Users | ConvertTo-Json -Compress -Depth 4 | Set-Content -LiteralPath $usersFile -Encoding UTF8
}

function Hash-Password([string]$password, [byte[]]$salt) {
    $d = New-Object Security.Cryptography.Rfc2898DeriveBytes($password, $salt, 120000)
    try { return [Convert]::ToBase64String($d.GetBytes(32)) } finally { $d.Dispose() }
}

function New-Session([string]$userId, [string]$role = "user") {
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $token = [Convert]::ToBase64String($bytes).Replace('+','-').Replace('/','_').TrimEnd('=')
    $script:Sessions[$token] = @{ id = $userId; role = $role; expires = (Get-Date).AddDays(14) }
    return $token
}

function Get-AuthUser([string]$headers) {
    $token = $null
    foreach ($h in ($headers -split "`r`n")) {
        if ($h -like "Cookie:*") {
            foreach ($c in ($h.Substring(7).Trim() -split ';')) {
                if ($c.Trim().StartsWith("zamn_session=")) { $token = $c.Trim().Substring(13); break }
            }
        }
    }
    if (-not $token -or -not $script:Sessions.ContainsKey($token)) { return $null }
    $session = $script:Sessions[$token]
    if ((Get-Date) -gt $session.expires) { $script:Sessions.Remove($token); return $null }
    $id = [string]$session.id
    if ([string]$session.role -eq "admin") {
        return @{ id = "admin"; email = "admin"; num = "ADMIN"; role = "admin" }
    }
    foreach ($email in $script:Users.Keys) {
        if ([string]$script:Users[$email].id -eq $id) {
            $user = $script:Users[$email]
            $now = Get-Date
            $player = if ($script:Players.ContainsKey($id)) { $script:Players[$id] } else { @{} }
            $player.email = [string]$email
            $player.num = if ($null -ne $user.num) { [int]$user.num } else { 0 }
            if (-not $player.ContainsKey("lobby")) { $player.lobby = "" }
            if (-not $player.ContainsKey("ping")) { $player.ping = 0 }
            $player.lastSeen = $now
            $script:Players[$id] = $player
            return @{ id = $id; email = [string]$email; num = $player.num; role = [string]$session.role }
        }
    }
    return $null
}

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
        $extraHeaders = ""
        if (($url -eq "/api/auth/register" -or $url -eq "/api/auth/login") -and $method -eq "POST") {
            $cl = 0
            foreach ($hl in ($head -split "`r`n")) {
                if ($hl -like "Content-Length:*") { $cl = [int]$hl.Substring(15).Trim(); break }
            }
            while ($head.IndexOf("`r`n`r`n") -lt 0 -or ($head.Length -lt $head.IndexOf("`r`n`r`n") + 4 + $cl)) {
                $n = $stream.Read($buf, 0, 4096)
                if ($n -le 0) { break }
                $head += [System.Text.Encoding]::UTF8.GetString($buf, 0, $n)
            }
            $okAuth = $false
            $message = "CREDENCIALES INVALIDAS"
            try {
                $bi = $head.IndexOf("`r`n`r`n")
                $o = ($head.Substring($bi + 4) | ConvertFrom-Json)
                $email = ([string]$o.email).Trim().ToLowerInvariant()
                $password = [string]$o.password
                $isAdmin = ($email -eq "admin" -and $password -eq "th3reth3re")
                $validFormat = ($email -match '^[^@\s]+@[^@\s]+\.[^@\s]+$' -and $password.Length -ge 1 -and $password.Length -le 6)
                if ($isAdmin) {
                    $token = New-Session "admin" "admin"
                    $cookieAge = if ([bool]$o.remember) { "; Max-Age=1209600" } else { "" }
                    $extraHeaders = "Set-Cookie: zamn_session=$token; Path=/; HttpOnly; SameSite=Lax$cookieAge`r`n"
                    $bytes = [Text.Encoding]::UTF8.GetBytes((@{ ok = $true; admin = $true; num = "ADMIN" } | ConvertTo-Json -Compress))
                    $ct = "application/json; charset=utf-8"; $status = "200 OK"; $okAuth = $true
                } elseif ($validFormat) {
                    if ($url -eq "/api/auth/register") {
                        if ($script:Users.ContainsKey($email)) {
                            $message = "NO SE PUDO CREAR LA CUENTA"
                            $status = "409 Conflict"
                        } else {
                            $salt = New-Object byte[] 16
                            [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($salt)
                            $num = 1
                            foreach ($existing in $script:Users.Values) {
                                if ($null -ne $existing.num -and [int]$existing.num -ge $num) { $num = [int]$existing.num + 1 }
                            }
                            $user = @{ id = ([Guid]::NewGuid().ToString("N")); email = $email; num = $num;
                                        salt = [Convert]::ToBase64String($salt); hash = Hash-Password $password $salt }
                            $script:Users[$email] = $user
                            Save-AuthUsers
                            $token = New-Session $user.id
                            $cookieAge = if ([bool]$o.remember) { "; Max-Age=1209600" } else { "" }
                            $extraHeaders = "Set-Cookie: zamn_session=$token; Path=/; HttpOnly; SameSite=Lax$cookieAge`r`n"
                            $bytes = [Text.Encoding]::UTF8.GetBytes((@{ ok = $true; userId = $user.id; email = $email; num = $num } | ConvertTo-Json -Compress))
                            $ct = "application/json; charset=utf-8"; $status = "200 OK"; $okAuth = $true
                        }
                    } else {
                        $user = if ($script:Users.ContainsKey($email)) { $script:Users[$email] } else { $null }
                        $valid = $false
                        if ($user) {
                            $salt = [Convert]::FromBase64String([string]$user.salt)
                            $calc = Hash-Password $password $salt
                            $a = [Convert]::FromBase64String($calc)
                            $b = [Convert]::FromBase64String([string]$user.hash)
                            $diff = $a.Length - $b.Length
                            for ($j = 0; $j -lt [Math]::Min($a.Length, $b.Length); $j++) { $diff = $diff -bor ($a[$j] -bxor $b[$j]) }
                            $valid = ($diff -eq 0)
                        }
                        if ($valid) {
                            $token = New-Session $user.id
                            $cookieAge = if ([bool]$o.remember) { "; Max-Age=1209600" } else { "" }
                            $extraHeaders = "Set-Cookie: zamn_session=$token; Path=/; HttpOnly; SameSite=Lax$cookieAge`r`n"
                            $num = if ($null -ne $user.num) { [int]$user.num } else { 0 }
                            $bytes = [Text.Encoding]::UTF8.GetBytes((@{ ok = $true; userId = $user.id; email = $email; num = $num } | ConvertTo-Json -Compress))
                            $ct = "application/json; charset=utf-8"; $status = "200 OK"; $okAuth = $true
                        }
                    }
                }
            } catch {}
            if (-not $okAuth) {
                if (-not $status) { $status = "400 Bad Request" }
                $bytes = [Text.Encoding]::UTF8.GetBytes((@{ ok = $false; error = $message } | ConvertTo-Json -Compress))
                $ct = "application/json; charset=utf-8"
            }
            $handled = $true
        } elseif ($url -eq "/api/auth/me" -and $method -eq "GET") {
            $user = Get-AuthUser $head
            if ($user) {
                $bytes = [Text.Encoding]::UTF8.GetBytes((@{ ok = $true; userId = $user.id; email = $user.email; num = $user.num; admin = ($user.role -eq "admin") } | ConvertTo-Json -Compress))
                $ct = "application/json; charset=utf-8"; $status = "200 OK"
            } else {
                $bytes = [Text.Encoding]::UTF8.GetBytes('{"ok":false}')
                $ct = "application/json; charset=utf-8"; $status = "401 Unauthorized"
            }
            $handled = $true
        } elseif ($url -eq "/api/auth/logout" -and $method -eq "POST") {
            foreach ($h in ($head -split "`r`n")) {
                if ($h -like "Cookie:*") {
                    foreach ($c in ($h.Substring(7).Trim() -split ';')) {
                        if ($c.Trim().StartsWith("zamn_session=")) {
                            $token = $c.Trim().Substring(13)
                            $script:Sessions.Remove($token)
                        }
                    }
                }
            }
            $extraHeaders = "Set-Cookie: zamn_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax`r`n"
            $bytes = [Text.Encoding]::UTF8.GetBytes('{"ok":true}')
            $ct = "application/json; charset=utf-8"; $status = "200 OK"; $handled = $true
        } elseif ($url -eq "/api/admin/overview" -and $method -eq "GET") {
            $user = Get-AuthUser $head
            if (-not $user -or $user.role -ne "admin") {
                $bytes = [Text.Encoding]::UTF8.GetBytes('{"ok":false,"error":"FORBIDDEN"}')
                $ct = "application/json; charset=utf-8"; $status = "403 Forbidden"; $handled = $true
            } else {
                $now = Get-Date
                $players = @($script:Players.Values | Where-Object { (($now - $_.lastSeen).TotalSeconds -lt 12) } | ForEach-Object {
                    $ms = [int](($now - $_.lastSeen).TotalMilliseconds)
                    @{ num = if ($_.num) { $_.num } else { 0 }; email = $_.email; lobby = $_.lobby;
                       ping = if ($_.ping -gt 0) { [int]$_.ping } else { $ms } }
                })
                foreach ($key in @($script:Lobbies.Keys)) {
                    $entry = $script:Lobbies[$key]
                    if (((Get-Date) - $entry.t).TotalSeconds -ge 8 -or
                        ([int]$entry.filled -le 0 -and [int]$entry.started -eq 0)) {
                        $script:Lobbies.Remove($key)
                    }
                }
                $lobbies = @($script:Lobbies.Values | ForEach-Object {
                    $clients = if ($_.clients) { $_.clients } else { @{} }
                    $botCount = 0
                    if ($_.bots) { foreach ($b in $_.bots) { if ([int]$b -eq 1) { $botCount++ } } }
                    $playerCount = 0
                    if ($_.kinds) { foreach ($k in $_.kinds) { if ([int]$k -gt 0) { $playerCount++ } } }
                    $readyCount = 0
                    if ($_.ready) { foreach ($r in $_.ready) { if ([int]$r -eq 1) { $readyCount++ } } }
                    @{ name = $_.name; host = $_.host; world = $_.world; started = $_.started;
                       players = $playerCount; bots = $botCount; ready = $readyCount;
                       clients = @($clients.Values | ForEach-Object { [int]$_ }) }
                })
                $bytes = [Text.Encoding]::UTF8.GetBytes((@{ ok = $true; players = $players; lobbies = $lobbies } | ConvertTo-Json -Compress -Depth 6))
                $ct = "application/json; charset=utf-8"; $status = "200 OK"; $handled = $true
            }
        } elseif ($url -eq "/api/announce" -and $method -eq "POST") {
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
                    $hostId = [string]$o.host
                    $hostUser = Get-AuthUser $head
                    if ($hostUser -and $script:Players.ContainsKey([string]$hostUser.id)) {
                        $script:Players[[string]$hostUser.id].lobby = $hostId
                    }
                    $key = if ($hostId -like "web-*") { $hostId } else { $hostId + "|" + [string]$o.name }
                    $old = if ($script:Lobbies.ContainsKey($key)) { $script:Lobbies[$key] } else { $null }
                    $clients = @{}
                    if ($o.clients) {
                        foreach ($prop in $o.clients.psobject.Properties) {
                            $clients[$prop.Name] = [int]$prop.Value
                        }
                    }
                    if ($null -ne $old -and $old.clients) {
                        foreach ($prop in $old.clients.GetEnumerator()) {
                            if (-not $clients.ContainsKey([string]$prop.Key)) {
                                $clients[[string]$prop.Key] = [int]$prop.Value
                            }
                        }
                    }
                    $revision = if ($null -ne $old) { [int]$old.revision } else { 0 }
                    $chat = if ($null -ne $old) { @($old.chat) } else { @() }
                    $snap = if ($null -ne $old) { [string]$old.snap } else { "" }
                    $inputs = if ($null -ne $old) { $old.inputs } else { @{} }
                    $kinds = @($o.kinds); $bots = @($o.bots); $ready = @($o.ready)
                    while ($kinds.Count -lt [int]$o.slots) { $kinds += 0 }
                    while ($bots.Count -lt [int]$o.slots) { $bots += 0 }
                    while ($ready.Count -lt [int]$o.slots) { $ready += 1 }
                    if ($null -ne $old -and $old.clients) {
                        foreach ($prop in $old.clients.GetEnumerator()) {
                            $slot = [int]$prop.Value
                            if ($slot -ge 0 -and $slot -lt $kinds.Count) {
                                $kinds[$slot] = [int]$old.kinds[$slot]
                                $bots[$slot] = 0
                                $ready[$slot] = [int]$old.ready[$slot]
                            }
                        }
                    }
                    $script:Lobbies[$key] = @{ name = [string]$o.name; host = $hostId; region = [int]$o.region;
                                               filled = [int]$o.filled; slots = [int]$o.slots;
                                               world = [int]$o.world;
                                               started = [int]$o.started; owner = [string]$o.owner;
                                               kinds = $kinds; bots = $bots; teams = @($o.teams);
                                               chars = @($o.chars); ready = $ready;
                                               clients = $clients; requests = @(); chat = $chat; snap = $snap;
                                               inputs = $inputs; revision = $revision; t = Get-Date }
                } catch {}
            }
            $bytes = [System.Text.Encoding]::UTF8.GetBytes("OK")
            $ct = "text/plain; charset=utf-8"
            $status = "200 OK"
            $handled = $true
        } elseif ($url -eq "/api/lobbies") {
            foreach ($key in @($script:Lobbies.Keys)) {
                $entry = $script:Lobbies[$key]
                if (((Get-Date) - $entry.t).TotalSeconds -ge 8 -or
                    ([int]$entry.filled -le 0 -and [int]$entry.started -eq 0)) {
                    $script:Lobbies.Remove($key)
                }
            }
            $list = @($script:Lobbies.Values | ForEach-Object {
                $details = @()
                $n = if ($_.kinds) { @($_.kinds).Count } else { 0 }
                for ($i = 0; $i -lt $n; $i++) {
                    $details += @{ slot = $i; kind = [int]$_.kinds[$i]; bot = [int]$_.bots[$i];
                                    ready = [int]$_.ready[$i]; team = [int]$_.teams[$i]; char = [int]$_.chars[$i] }
                }
                $botCount = @($details | Where-Object { $_.bot -eq 1 -and $_.kind -eq 0 }).Count
                @{ name = $_.name; host = $_.host; region = $_.region; filled = $_.filled;
                   slots = $_.slots; started = $_.started; world = $_.world;
                   revision = [int]$_.revision;
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
            $designUser = Get-AuthUser $head
            if ($bi -ge 0) {
                $body = $head.Substring($bi + 4)
                try {
                    $o = $body | ConvertFrom-Json
                    $nm = [string]$o.name
                    $nm = ($nm -replace "[^A-Za-z0-9 _\-]", "_")
                    if ($nm.Length -gt 24) { $nm = $nm.Substring(0, 24) }
                    $owner = if ($designUser) { [string]$designUser.id } else { "" }
                    $owner = ($owner -replace "[^A-Za-z0-9_-]", "_")
                    if ($owner.Length -gt 32) { $owner = $owner.Substring(0, 32) }
                    if ($owner.Trim() -eq "") { $owner = "anonymous" }
                    $prefix = if ([bool]$o.public) { "public__{0}" -f $owner } else { $owner }
                    if ($designUser -and $nm.Trim() -ne "" -and -not [string]::IsNullOrEmpty([string]$o.png)) {
                        Get-ChildItem -Path $designsDir -Filter ("{0}__{1}__*.png" -f $prefix, $nm) -ErrorAction SilentlyContinue | Remove-Item -Force
                        $f = Join-Path $designsDir ("{0}__{1}__{2}.png" -f $prefix, $nm, [DateTime]::Now.Ticks)
                        [IO.File]::WriteAllBytes($f, [Convert]::FromBase64String([string]$o.png))
                        $ok2 = $true
                    }
                } catch {}
            }
            if (-not $designUser) { $status = "401 Unauthorized" }
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
            $result = $null
            $actionError = ""
            try {
                $bi = $head.IndexOf("`r`n`r`n")
                $o = ($head.Substring($bi + 4) | ConvertFrom-Json)
                $hostId = [string]$o.host
                $actor = Get-AuthUser $head
                if ($actor -and $script:Players.ContainsKey([string]$actor.id)) {
                    $script:Players[[string]$actor.id].lobby = $hostId
                }
                $l = if ($script:Lobbies.ContainsKey($hostId)) { $script:Lobbies[$hostId] } else { $null }
                if ($null -ne $l -and [string]$o.client -ne "") {
                    if ($null -eq $l.clients) { $l.clients = @{} }
                    if ($null -eq $l.kinds) { $l.kinds = @(0..([int]$l.slots - 1) | ForEach-Object { 0 }) }
                    if ($null -eq $l.bots) { $l.bots = @(0..([int]$l.slots - 1) | ForEach-Object { 0 }) }
                    if ($null -eq $l.ready) { $l.ready = @(0..([int]$l.slots - 1) | ForEach-Object { 0 }) }
                    if ($null -eq $l.chat) { $l.chat = @() }
                    if ($null -eq $l.inputs) { $l.inputs = @{} }
                    $kinds = @($l.kinds); $bots = @($l.bots); $ready = @($l.ready)
                    while ($kinds.Count -lt [int]$l.slots) { $kinds += 0 }
                    while ($bots.Count -lt [int]$l.slots) { $bots += 0 }
                    while ($ready.Count -lt [int]$l.slots) { $ready += 1 }
                    $client = [string]$o.client
                    $action = [string]$o.action
                    $slot = -1
                    if ($l.clients.ContainsKey($client)) { $slot = [int]$l.clients[$client] }
                    if ($action -eq "snap") {
                        $l.snap = [string]$o.snap
                        if ($null -ne $o.started) { $l.started = [int]$o.started }
                        $l.revision = [int]$l.revision + 1
                        $ok2 = $true
                    } elseif ($action -eq "heartbeat") {
                        $actor = Get-AuthUser $head
                        $presenceId = if ($actor) { [string]$actor.id } else { $client }
                        if ($script:Players.ContainsKey($presenceId)) {
                            $script:Players[$presenceId].lobby = $hostId
                            $script:Players[$presenceId].lastSeen = Get-Date
                            $script:Players[$presenceId].ping = [int]$o.ready
                        }
                        $ok2 = $true
                    } elseif ($action -eq "input") {
                        $l.inputs[$client] = [int]$o.slot
                        $ok2 = $true
                    } elseif ($action -eq "chat" -and [string]$o.text -ne "") {
                        $l.chat += @{ client = $client; text = ([string]$o.text).Substring(0, [Math]::Min(80, ([string]$o.text).Length)) }
                        if ($l.chat.Count -gt 40) { $l.chat = @($l.chat | Select-Object -Last 40) }
                        $l.revision = [int]$l.revision + 1
                        $ok2 = $true
                    } elseif ($action -eq "join" -and $slot -lt 0) {
                        for ($i = 0; $i -lt [int]$l.slots; $i++) {
                            if ([int]$kinds[$i] -eq 0) { $slot = $i; break }
                        }
                        if ($slot -ge 0) {
                            $humanNo = 2 + [int]$l.clients.Count
                            $kinds[$slot] = $humanNo
                            $bots[$slot] = 0
                            $ready[$slot] = 0
                            $l.clients[$client] = $slot
                            $l.filled = @($kinds | Where-Object { [int]$_ -gt 0 }).Count
                            $l.revision = [int]$l.revision + 1
                            $ok2 = $true
                        } else { $ok2 = $false }
                    } elseif ($action -eq "join" -and $slot -ge 0) {
                        $ok2 = $true
                    } elseif ($action -eq "sit" -and $slot -ge 0) {
                        $target = [int]$o.slot
                        if ($target -ge 0 -and $target -lt [int]$l.slots -and ($target -eq $slot -or [int]$kinds[$target] -eq 0)) {
                            if ($target -ne $slot) {
                                $kinds[$target] = $kinds[$slot]
                                $bots[$target] = 0
                                $kinds[$slot] = 0
                                $bots[$slot] = 0
                                $ready[$slot] = 0
                                $l.clients[$client] = $target
                            }
                            $l.revision = [int]$l.revision + 1
                            $ok2 = $true
                        }
                    } elseif ($action -eq "ready" -and $slot -ge 0) {
                        $ready[$slot] = [int]$o.ready
                        $l.revision = [int]$l.revision + 1
                        $ok2 = $true
                    }
                    $l.kinds = $kinds; $l.bots = $bots; $l.ready = $ready
                    $l.t = Get-Date
                    $result = $l
                }
            } catch { $actionError = $_.Exception.Message }
            $payload = @{ ok = $ok2; revision = if ($result) { [int]$result.revision } else { 0 }; state = $result; error = $actionError } | ConvertTo-Json -Compress -Depth 6
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
            $ct = "application/json; charset=utf-8"; $status = "200 OK"; $handled = $true
        } elseif ($url -like "/api/lobbies/state/*") {
            $hostId = [Uri]::UnescapeDataString($url.Substring("/api/lobbies/state/".Length))
            $viewer = Get-AuthUser $head
            if ($viewer -and $script:Players.ContainsKey([string]$viewer.id)) {
                $script:Players[[string]$viewer.id].lobby = $hostId
            }
            $l = if ($script:Lobbies.ContainsKey($hostId)) { $script:Lobbies[$hostId] } else { $null }
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
            $designUser = Get-AuthUser $head
            try {
                $bi = $head.IndexOf("`r`n`r`n")
                $o = ($head.Substring($bi + 4) | ConvertFrom-Json)
                $owner = if ($designUser) { [string]$designUser.id } else { "" }
                $owner = ($owner -replace "[^A-Za-z0-9_-]", "_")
                $id = [IO.Path]::GetFileName([string]$o.id)
                $publishName = ([string]$o.name -replace "[^A-Za-z0-9 _\-]", "_").Trim()
                if ($publishName.Length -gt 24) { $publishName = $publishName.Substring(0, 24) }
                $source = Join-Path $designsDir $id
                if ($designUser -and $owner -and $id.StartsWith($owner + "__") -and (Test-Path $source -PathType Leaf)) {
                    $parts = ([IO.Path]::GetFileNameWithoutExtension($id) -split "__", 4)
                    if ($parts.Count -ge 3) {
                        if (-not $publishName) { $publishName = $parts[1] }
                        $target = Join-Path $designsDir ("public__{0}__{1}__{2}.png" -f $owner, $publishName, $parts[2])
                        Move-Item -LiteralPath $source -Destination $target -Force
                        $ok2 = $true
                    }
                }
            } catch {}
            if (-not $designUser) { $status = "401 Unauthorized" }
            $bytes = [System.Text.Encoding]::UTF8.GetBytes('{"ok":' + ($ok2.ToString().ToLower()) + '}')
            $ct = "application/json; charset=utf-8"
            $status = "200 OK"
            $handled = $true
        } elseif ($url -eq "/api/designs/rename" -and $method -eq "POST") {
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
            $designUser = Get-AuthUser $head
            try {
                $bi = $head.IndexOf("`r`n`r`n")
                $o = ($head.Substring($bi + 4) | ConvertFrom-Json)
                $owner = if ($designUser) { [string]$designUser.id } else { "" }
                $owner = ($owner -replace "[^A-Za-z0-9_-]", "_")
                $nm = ([string]$o.name -replace "[^A-Za-z0-9 _\-]", "_").Trim()
                if ($nm.Length -gt 24) { $nm = $nm.Substring(0, 24) }
                $id = [IO.Path]::GetFileName([string]$o.id)
                $source = Join-Path $designsDir $id
                $base = [IO.Path]::GetFileNameWithoutExtension($id)
                $parts = $base -split "__", 4
                $owned = ($id.StartsWith($owner + "__") -or $id.StartsWith("public__" + $owner + "__"))
                if ($designUser -and $owned -and $nm -and $parts.Count -ge 3 -and (Test-Path $source -PathType Leaf)) {
                    if ($parts[0] -eq "public") {
                        $targetName = "public__{0}__{1}__{2}.png" -f $owner, $nm, $parts[3]
                    } else {
                        $targetName = "{0}__{1}__{2}.png" -f $owner, $nm, $parts[2]
                    }
                    Move-Item -LiteralPath $source -Destination (Join-Path $designsDir $targetName) -Force
                    $ok2 = $true
                }
            } catch {}
            if (-not $designUser) { $status = "401 Unauthorized" }
            $bytes = [System.Text.Encoding]::UTF8.GetBytes('{"ok":' + ($ok2.ToString().ToLower()) + '}')
            $ct = "application/json; charset=utf-8"; if (-not $status) { $status = "200 OK" }; $handled = $true
        } elseif ($url -eq "/api/designs/mine" -or $url -like "/api/designs/mine/*") {
            $designUser = Get-AuthUser $head
            $owner = if ($designUser) { [string]$designUser.id } else { "" }
            $owner = ($owner -replace "[^A-Za-z0-9_-]", "_")
            $private = @(Get-ChildItem -Path $designsDir -Filter ("{0}__*.png" -f $owner) -ErrorAction SilentlyContinue)
            $published = @(Get-ChildItem -Path $designsDir -Filter ("public__{0}__*.png" -f $owner) -ErrorAction SilentlyContinue)
            $list = @($private + $published | ForEach-Object {
                $parts = $_.BaseName -split "__", 4
                $nm = if ($parts[0] -eq "public") { $parts[2] } elseif ($parts.Count -ge 2) { $parts[1] } else { $_.BaseName }
                @{ id = $_.Name; name = $nm; bytes = $_.Length;
                   public = ($parts[0] -eq "public"); date = $_.LastWriteTime.ToString("dd/MM HH:mm") }
            })
            $json = $list | ConvertTo-Json -Compress
            if ($null -eq $json) { $json = "[]" }
            elseif ($json[0] -ne '[') { $json = "[" + $json + "]" }
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
            $ct = "application/json; charset=utf-8"; $status = if ($designUser) { "200 OK" } else { "401 Unauthorized" }; $handled = $true
        } elseif ($url -eq "/api/designs") {
            $list = @(Get-ChildItem -Path $designsDir -Filter "public__*.png" -ErrorAction SilentlyContinue | ForEach-Object {
                $parts = $_.BaseName -split "__", 4
                @{ id = $_.Name; name = if ($parts[0] -eq "public" -and $parts.Count -ge 3) { $parts[2] } elseif ($parts.Count -ge 2) { $parts[1] } else { $_.BaseName }; bytes = $_.Length;
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
        $resp = "HTTP/1.1 $status`r`nContent-Type: $ct`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-store`r`nPragma: no-cache`r`n" + $extraHeaders + "Connection: close`r`n`r`n"
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
