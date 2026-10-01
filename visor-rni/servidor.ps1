<#
  Servidor estatico minimo del visor RNI.

  Existe para que no haya que instalar nada: usa Windows PowerShell, que viene
  con Windows 10 o superior. El visor necesita http:// porque los modulos ES
  y el motor SQLite en WebAssembly no se cargan desde file:// (doble clic).

  El texto va en ASCII a proposito: Windows PowerShell 5.1 lee los .ps1 segun
  el codigo de pagina de la consola y las tildes se romperian.
#>

param(
    [int]$Puerto = 8090,
    [switch]$SinAbrir
)

$ErrorActionPreference = 'Stop'

# Extension -> tipo de contenido. Los dos que no se pueden adivinar:
#   .wasm   el navegador exige "application/wasm" para compilar en streaming
#   .woff2  el navegador exige el tipo correcto para cargar la fuente
$mime = @{
    '.html'  = 'text/html; charset=utf-8'
    '.js'    = 'text/javascript; charset=utf-8'
    '.css'   = 'text/css; charset=utf-8'
    '.json'  = 'application/json; charset=utf-8'
    '.md'    = 'text/plain; charset=utf-8'
    '.txt'   = 'text/plain; charset=utf-8'
    '.wasm'  = 'application/wasm'
    '.woff2' = 'font/woff2'
    '.woff'  = 'font/woff'
    '.ttf'   = 'font/ttf'
    '.otf'   = 'font/otf'
    '.png'   = 'image/png'
    '.jpg'   = 'image/jpeg'
    '.jpeg'  = 'image/jpeg'
    '.gif'   = 'image/gif'
    '.webp'  = 'image/webp'
    '.svg'   = 'image/svg+xml'
    '.ico'   = 'image/x-icon'
    '.db'    = 'application/octet-stream'
    '.zip'   = 'application/zip'
}

$raiz = $PSScriptRoot.TrimEnd('\')
$prefijo = $raiz + '\'
$url = "http://localhost:$Puerto/"

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add($url)

try {
    $listener.Start()
}
catch {
    Write-Host ""
    Write-Host "  No pude usar el puerto ${Puerto}: ya esta en uso."
    Write-Host "  Cerra la otra ventana del visor e intenta de nuevo."
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "  Visor RNI"
Write-Host "  Servidor: $url"
Write-Host "  Carpeta:  $raiz"
Write-Host "  Cortalo con Ctrl+C o cerrando esta ventana."
Write-Host ""

if (-not $SinAbrir) { Start-Process $url }

function Responder($ctx, $codigo, $tipo, $bytes) {
    $res = $ctx.Response
    try {
        $res.StatusCode = $codigo
        $res.ContentType = $tipo
        $res.ContentLength64 = $bytes.Length
        $res.Headers['Cache-Control'] = 'no-store'
        if ($ctx.Request.HttpMethod -ne 'HEAD' -and $bytes.Length -gt 0) {
            $res.OutputStream.Write($bytes, 0, $bytes.Length)
        }
    }
    finally { $res.Close() }
}

try {
    while ($listener.IsListening) {
        $ctx = $listener.GetContext()
        try {
            $req = $ctx.Request

            if ($req.HttpMethod -ne 'GET' -and $req.HttpMethod -ne 'HEAD') {
                Responder $ctx 405 'text/plain; charset=utf-8' `
                    ([System.Text.Encoding]::ASCII.GetBytes('405 Method Not Allowed'))
                continue
            }

            $ruta = [Uri]::UnescapeDataString($req.Url.AbsolutePath)
            if ($ruta -eq '' -or $ruta -eq '/') { $ruta = '/index.html' }

            $relativa = $ruta.TrimStart('/').Replace('/', '\')
            $rutaLocal = [System.IO.Path]::GetFullPath((Join-Path $raiz $relativa))

            if ($rutaLocal -ne $raiz -and
                -not $rutaLocal.StartsWith($prefijo, [System.StringComparison]::OrdinalIgnoreCase)) {
                Responder $ctx 403 'text/plain; charset=utf-8' `
                    ([System.Text.Encoding]::ASCII.GetBytes('403 Forbidden'))
                continue
            }

            if (-not [System.IO.File]::Exists($rutaLocal)) {
                Responder $ctx 404 'text/plain; charset=utf-8' `
                    ([System.Text.Encoding]::ASCII.GetBytes("404 Not Found: $relativa"))
                continue
            }

            $ext = [System.IO.Path]::GetExtension($rutaLocal).ToLowerInvariant()
            $tipo = $mime[$ext]
            if (-not $tipo) { $tipo = 'application/octet-stream' }

            # Se sirve por Content-Length con CopyTo: asi los archivos grandes
            # (el xlsx de 861 KB o una base de prueba) no se cargan enteros en
            # memoria y el navegador puede ir leyendo mientras se escribe.
            $fs = $null
            try {
                $fs = [System.IO.File]::OpenRead($rutaLocal)
                $res = $ctx.Response
                $res.StatusCode = 200
                $res.ContentType = $tipo
                $res.ContentLength64 = $fs.Length
                $res.Headers['Cache-Control'] = 'no-store'
                if ($req.HttpMethod -ne 'HEAD') { $fs.CopyTo($res.OutputStream) }
            }
            finally {
                if ($fs) { $fs.Dispose() }
                $ctx.Response.Close()
            }
        }
        catch {
            Write-Host ("  error: " + $_.Exception.Message)
            try { Responder $ctx 500 'text/plain; charset=utf-8' `
                ([System.Text.Encoding]::ASCII.GetBytes('500 Internal Server Error')) } catch { }
        }
    }
}
finally {
    try { $listener.Stop() } catch { }
    try { $listener.Close() } catch { }
    Write-Host ""
    Write-Host "  Servidor detenido."
}
