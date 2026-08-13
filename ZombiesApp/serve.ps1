# Zombies Ate My Neighbors - standalone launcher server
# Serves the app folder over localhost and opens the default browser.
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
    ".ico"  = "image/x-icon"
}

# Find a free port starting at 8437
$port = 8437
while ($true) {
    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add("http://localhost:$port/")
    try { $listener.Start(); break }
    catch { $listener.Close(); $port++ ; if ($port -gt 8500) { throw "No free port found." } }
}

Write-Host ""
Write-Host "  ZOMBIES ATE MY NEIGHBORS is running at http://localhost:$port/" -ForegroundColor Green
Write-Host "  Keep this window open while playing. Close it to quit." -ForegroundColor DarkGray
Write-Host ""

Start-Process "http://localhost:$port/"

while ($listener.IsListening) {
    $ctx = $listener.GetContext()
    try {
        $rel = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath).TrimStart("/")
        if ($rel -eq "") { $rel = "index.html" }
        $path = Join-Path $root $rel
        # Prevent path traversal outside the app folder
        $full = [IO.Path]::GetFullPath($path)
        if (-not $full.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path $full -PathType Leaf)) {
            $ctx.Response.StatusCode = 404
            $ctx.Response.Close()
            continue
        }
        $bytes = [IO.File]::ReadAllBytes($full)
        $ext = [IO.Path]::GetExtension($full).ToLower()
        $ctx.Response.ContentType = if ($mime.ContainsKey($ext)) { $mime[$ext] } else { "application/octet-stream" }
        $ctx.Response.ContentLength64 = $bytes.Length
        if ($ctx.Request.HttpMethod -ne "HEAD") {
            $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
        }
        $ctx.Response.Close()
    } catch {
        try { $ctx.Response.StatusCode = 500; $ctx.Response.Close() } catch {}
    }
}
