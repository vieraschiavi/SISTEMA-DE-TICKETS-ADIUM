# (c) 2026 Martin Viera. Todos los derechos reservados.
#
# Adium All in One - conseguir un Python que sirva, sin pedirle nada a nadie.
#
# Por que existe
# --------------
# En una laptop sin Python el .bat decia "Falta Python 3.11 o superior,
# descargalo de python.org" y se quedaba ahi. En una PC corporativa eso es
# un pedido a IT y una semana. Este script lo resuelve solo:
#
#   1. Un Python que ya este y sirva (3.11 a 3.13): el "python-runtime" que
#      viene en el paquete, el que este script ya bajo antes, "py -3.11/12/13"
#      o el python del PATH.
#   2. Si no hay, baja uno, probando tres origenes en orden:
#      a) el paquete OFICIAL de nuget.org (lo publica el equipo de
#         python.org): un .zip con Python entero, sin instalador;
#      b) python-build-standalone en GitHub (el mismo Python que usa "uv"):
#         GitHub casi nunca esta bloqueado, porque de ahi se bajo el programa;
#      c) el instalador de python.org, silencioso y SOLO para este usuario.
#      Ninguno pide administrador ni toca el registro: todo queda en la
#      carpeta del usuario y se borra a mano.
#
# Modo de lenguaje restringido (lo que rompio la primera version)
# ---------------------------------------------------------------
# En una PC corporativa con AppLocker o WDAC, PowerShell corre en
# "ConstrainedLanguage": no deja invocar metodos .NET como
# [IO.File]::ReadAllText o [Console]::Error.WriteLine. La primera version
# usaba los dos y moria en la primera linea, SIN dejar rastro: el error se lo
# tragaba el "for /f" del .bat y la persona veia "no se pudo" sin motivo.
# Por eso, ahora:
#   - Solo cmdlets y operadores de PowerShell; ningun metodo .NET que no sea
#     de string (y los que puedan faltar, adentro de try).
#   - Todo lo que se le cuenta a la persona va a un LOG (ADIUM_LOG) que el
#     .bat muestra siempre. Por la salida estandar sale UNA linea y nada mas.
#   - Hay un test que corre este script en ConstrainedLanguage de verdad.
#
# Contrato con el .bat: por la salida estandar sale UNA linea,
#   "propio|C:\...\python.exe"   (lo bajo este script: se instala adentro)
#   "sistema|C:\...\python.exe"  (ya estaba: el .bat arma un venv aparte)
# Sale 1 si no consiguio ninguno, con el motivo en el log.
#
# Variables (todas las pone el .bat):
#   ADIUM_BASE            carpeta del usuario donde vive el Python propio
#   ADIUM_LOG             archivo donde se cuenta lo que pasa
#   ADIUM_RUNTIME_LOCAL   carpeta "python-runtime" del paquete, si viene
#   ADIUM_PYTHON_PROPIO=1 no usar el Python del sistema aunque sirva
#   ADIUM_PY_VERSION      por defecto 3.11.9 (la ultima 3.11 con binarios)
#   ADIUM_PY_NUGET / ADIUM_PY_GITHUB / ADIUM_PY_ORG   origen de las descargas
#                         (para pruebas y para un espejo interno de la empresa)

$ErrorActionPreference = 'Continue'        # cada cmdlet que importa lleva -ErrorAction Stop
$ProgressPreference = 'SilentlyContinue'   # sin esto Invoke-WebRequest es 10x mas lento

$Version = if ($env:ADIUM_PY_VERSION) { $env:ADIUM_PY_VERSION } else { '3.11.9' }
$Base = if ($env:ADIUM_BASE) { $env:ADIUM_BASE } else { Join-Path $env:LOCALAPPDATA 'Adium All in One' }
$Log = if ($env:ADIUM_LOG) { $env:ADIUM_LOG } else { Join-Path $Base 'conseguir_python.log' }
$Nuget = if ($env:ADIUM_PY_NUGET) { $env:ADIUM_PY_NUGET.TrimEnd('/') } else { 'https://www.nuget.org/api/v2/package' }
$Github = if ($env:ADIUM_PY_GITHUB) { $env:ADIUM_PY_GITHUB.TrimEnd('/') } else { 'https://github.com/astral-sh/python-build-standalone/releases/download' }
$Org = if ($env:ADIUM_PY_ORG) { $env:ADIUM_PY_ORG.TrimEnd('/') } else { 'https://www.python.org/ftp/python' }
# La version de python-build-standalone que trae 3.11.9 (release del 26/07/2024).
$GithubTag = '20240726'
$EnWindows = -not ($IsLinux -or $IsMacOS)   # en Windows PowerShell 5.1 las dos son $null

New-Item -ItemType Directory -Path $Base -Force -ErrorAction SilentlyContinue | Out-Null
Set-Content -LiteralPath $Log -Value '' -ErrorAction SilentlyContinue

function Decir([string]$texto) {
    Add-Content -LiteralPath $Log -Value $texto -ErrorAction SilentlyContinue
}

function Salir([string]$tipo, [string]$exe) {
    Write-Output "$tipo|$exe"
    exit 0
}

# Cualquier error que se escape queda en el log, no en la nada.
trap {
    Decir "  [X] Error inesperado en conseguir_python: $_"
    exit 1
}

Decir "  PowerShell $($PSVersionTable.PSVersion), modo $($ExecutionContext.SessionState.LanguageMode)"

$script:bloqueado = $false

function Probar([string]$exe, [string[]]$antes = @()) {
    # Devuelve la ruta real del python si la version sirve, o $null.
    if (-not $exe) { return $null }
    # El "python.exe" de WindowsApps es un atajo a la Microsoft Store, no un
    # Python: correrlo abre la tienda o sale con 9009.
    if ($exe -like '*\WindowsApps\*') { return $null }
    $codigo = "import sys; print(sys.executable); print('%d.%d' % sys.version_info[:2]); print('ok' if (3, 11) <= sys.version_info[:2] < (3, 14) else 'no')"
    try {
        $salida = & $exe @antes -c $codigo 2>$null
    } catch {
        # Aca cae el "este programa esta bloqueado por la directiva de grupo":
        # el archivo esta, pero Windows no lo deja ejecutar.
        $msg = "$_"
        if ($msg -match 'bloquead|blocked|directiva|policy|AppLocker|Control de aplicaciones|Application Control') {
            $script:bloqueado = $true
        }
        Decir "   (${exe}: no arranca: $msg)"
        return $null
    }
    if ($LASTEXITCODE -ne 0 -or -not $salida) { return $null }
    $lineas = @($salida)
    if ($lineas.Count -lt 3) { return $null }
    $ver = "$($lineas[1])".Trim()
    if ("$($lineas[2])".Trim() -eq 'ok') {
        if ($antes.Count -gt 0) { return "$($lineas[0])".Trim() }   # el lanzador "py" dice cual es
        return (Resolve-Path -LiteralPath $exe).Path
    }
    Decir "   (${exe} es Python ${ver}: no sirve, se necesita 3.11 a 3.13)"
    return $null
}

function Buscar-En([string]$carpeta) {
    if (-not $carpeta -or -not (Test-Path -LiteralPath $carpeta)) { return $null }
    foreach ($rel in @('python.exe', 'tools\python.exe', 'tools/python.exe', 'python\python.exe', 'python/python.exe')) {
        $p = Join-Path $carpeta $rel
        if (Test-Path -LiteralPath $p) { return $p }
    }
    $hallado = Get-ChildItem -LiteralPath $carpeta -Recurse -Filter 'python.exe' -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($hallado) { return $hallado.FullName }
    return $null
}

function Con-Pip([string]$exe) {
    # El paquete de nuget trae ensurepip pero no pip instalado.
    & $exe -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Decir '   Preparando pip...'
        & $exe -m ensurepip --default-pip *> $null
    }
    & $exe -m pip --version *> $null
    return ($LASTEXITCODE -eq 0)
}

function Proxy-Sistema {
    # El proxy que configuro la empresa, del registro. Si es un .pac no hay
    # forma de darselo a curl: ahi lo resuelve Invoke-WebRequest, que usa la
    # configuracion de Windows entera.
    try {
        $ie = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction Stop
        if ($ie.ProxyEnable -ne 1 -or -not $ie.ProxyServer) { return $null }
        $srv = "$($ie.ProxyServer)"
        if ($srv -match 'https=([^;]+)') { $srv = $Matches[1] }
        elseif ($srv -match 'http=([^;]+)') { $srv = $Matches[1] }
        if ($srv -notmatch '://') { $srv = "http://$srv" }
        return $srv
    } catch { return $null }
}

function Bajar([string]$url, [string]$destino) {
    Decir "   Descargando $url"
    $errores = @()
    # 1) curl.exe: viene con Windows 10/11, usa el almacen de certificados de
    #    Windows (anda con la inspeccion TLS de la empresa) y, con
    #    --proxy-negotiate -U :, se autentica en el proxy con el usuario de
    #    Windows. --ssl-no-revoke porque detras de un proxy la consulta de
    #    revocacion suele no llegar y curl corta.
    #    En Windows PowerShell "curl" a secas es un alias de Invoke-WebRequest:
    #    por eso curl.exe, con la extension.
    $nombreCurl = if ($EnWindows) { 'curl.exe' } else { 'curl' }
    $curl = Get-Command $nombreCurl -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($env:ADIUM_SIN_CURL -eq '1') { $curl = $null }      # para probar el otro camino
    if ($curl) {
        $args_ = @('-fsSL', '--retry', '2', '--connect-timeout', '30', '-o', $destino)
        if ($EnWindows) { $args_ += '--ssl-no-revoke' }
        $proxy = Proxy-Sistema
        if ($proxy) { $args_ += @('--proxy', $proxy, '--proxy-negotiate', '-U', ':') }
        $salida = & $curl.Source @args_ $url 2>&1
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $destino)) { return }
        $errores += "curl: $(($salida | Out-String).Trim())"
    }
    # 2) Invoke-WebRequest: usa la configuracion de proxy de Windows (incluido
    #    el .pac). TLS 1.2 se pide adentro de try: en modo restringido no se
    #    puede y en Windows 11 ya viene por defecto.
    try { [Net.ServicePointManager]::SecurityProtocol = 'Tls12' } catch { }
    try {
        $p = @{ Uri = $url; OutFile = $destino; UseBasicParsing = $true; ErrorAction = 'Stop' }
        # Las credenciales de Windows solo por https (PowerShell 7 las
        # rechaza por http, y ningun origen real es http).
        if ($url -like 'https:*') { $p.UseDefaultCredentials = $true }
        $proxy = Proxy-Sistema
        if ($proxy) { $p.Proxy = $proxy; $p.ProxyUseDefaultCredentials = $true }
        Invoke-WebRequest @p
        return
    } catch {
        $errores += "Invoke-WebRequest: $($_.Exception.Message)"
    }
    throw ($errores -join ' | ')
}

function Descomprimir([string]$archivo, [string]$destino) {
    New-Item -ItemType Directory -Path $destino -Force | Out-Null
    # tar.exe viene con Windows 10/11 y abre .zip y .tar.gz; Expand-Archive
    # queda de respaldo para el .zip.
    $tar = Get-Command tar -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($tar) {
        & $tar.Source -xf $archivo -C $destino 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { return }
    }
    if ($archivo -like '*.zip') {
        Expand-Archive -LiteralPath $archivo -DestinationPath $destino -Force -ErrorAction Stop
        return
    }
    throw "no se pudo descomprimir $archivo"
}

function Arquitectura {
    switch ($env:PROCESSOR_ARCHITECTURE) {
        'ARM64' { return @{ nuget = 'pythonarm64'; org = '-arm64.exe'; github = 'aarch64-pc-windows-msvc' } }
        'x86'   { return @{ nuget = 'pythonx86';   org = '.exe';       github = 'i686-pc-windows-msvc' } }
        default { return @{ nuget = 'python';      org = '-amd64.exe'; github = 'x86_64-pc-windows-msvc' } }
    }
}

function Listo-En([string]$carpeta, [string]$origen) {
    # Busca el python.exe, lo prueba y le deja pip. Devuelve la ruta o $null.
    $exe = Buscar-En $carpeta
    if (-not $exe) { return $null }
    if (-not $EnWindows) { chmod +x $exe }                  # solo para probarlo fuera de Windows
    $exe = Probar $exe
    if ($exe -and (Con-Pip $exe)) { return $exe }
    return $null
}

# ---------------------------------------------------------------------------
# 1. Lo que ya esta
# ---------------------------------------------------------------------------
$propios = @($env:ADIUM_RUNTIME_LOCAL, (Join-Path $Base 'python'),
             (Join-Path $Base 'python-gh'), (Join-Path $Base 'python-org'))
foreach ($carpeta in $propios) {
    $exe = Probar (Buscar-En $carpeta)
    if ($exe -and (Con-Pip $exe)) { Salir 'propio' $exe }
}

if ($env:ADIUM_PYTHON_PROPIO -ne '1') {
    if (Get-Command py -CommandType Application -ErrorAction SilentlyContinue) {
        foreach ($v in @('-3.11', '-3.12', '-3.13')) {
            $exe = Probar 'py' @($v)
            if ($exe) { Salir 'sistema' $exe }
        }
    }
    foreach ($nombre in @('python', 'python3')) {
        foreach ($cmd in @(Get-Command $nombre -All -CommandType Application -ErrorAction SilentlyContinue)) {
            $exe = Probar $cmd.Source
            if ($exe) { Salir 'sistema' $exe }
        }
    }
}

# ---------------------------------------------------------------------------
# 2. Bajar uno propio
# ---------------------------------------------------------------------------
Decir ''
Decir '  Esta PC no tiene Python 3.11 a 3.13: se baja uno propio, por unica vez.'
Decir "  Queda en $Base y no toca nada del sistema."
$arq = Arquitectura
$carpetaTmp = if ($env:TEMP) { $env:TEMP } else { $Base }
$tmp = Join-Path $carpetaTmp ("adium-python-" + (Get-Random))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$motivos = @()

# a) nuget.org
try {
    $zip = Join-Path $tmp "$($arq.nuget).$Version.zip"
    Bajar "$Nuget/$($arq.nuget)/$Version" $zip
    $destino = Join-Path $Base 'python'
    if (Test-Path -LiteralPath $destino) { Remove-Item -LiteralPath $destino -Recurse -Force }
    Descomprimir $zip $destino
    $exe = Listo-En $destino 'nuget.org'
    if ($exe) { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue; Salir 'propio' $exe }
    $motivos += 'nuget.org: el paquete se bajo pero no arranca'
} catch {
    $motivos += "nuget.org: $_"
}

# b) GitHub (python-build-standalone)
if (-not $script:bloqueado) {
    try {
        $nombreGh = "cpython-$Version%2B$GithubTag-$($arq.github)-install_only.tar.gz"
        $tgz = Join-Path $tmp "cpython-$Version.tar.gz"
        Bajar "$Github/$GithubTag/$nombreGh" $tgz
        $destino = Join-Path $Base 'python-gh'
        if (Test-Path -LiteralPath $destino) { Remove-Item -LiteralPath $destino -Recurse -Force }
        Descomprimir $tgz $destino
        $exe = Listo-En $destino 'GitHub'
        if ($exe) { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue; Salir 'propio' $exe }
        $motivos += 'github.com: el paquete se bajo pero no arranca'
    } catch {
        $motivos += "github.com: $_"
    }
}

# c) Instalador de python.org, silencioso y solo para este usuario
if (-not $script:bloqueado) {
    try {
        $instalador = Join-Path $tmp "python-$Version$($arq.org)"
        Bajar "$Org/$Version/python-$Version$($arq.org)" $instalador
        if (-not $EnWindows) { chmod +x $instalador }        # solo para probarlo fuera de Windows
        $destino = Join-Path $Base 'python-org'
        $argumentos = @('/quiet', 'InstallAllUsers=0', "TargetDir=`"$destino`"",
                        'Include_launcher=0', 'Include_test=0', 'Include_doc=0',
                        'Shortcuts=0', 'AssociateFiles=0', 'PrependPath=0', 'Include_pip=1')
        $proc = Start-Process -FilePath $instalador -ArgumentList $argumentos -Wait -PassThru -ErrorAction Stop
        if ($proc.ExitCode -ne 0) { throw "el instalador salio con codigo $($proc.ExitCode)" }
        $exe = Listo-En $destino 'python.org'
        if ($exe) { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue; Salir 'propio' $exe }
        $motivos += 'python.org: se instalo pero no arranca'
    } catch {
        $motivos += "python.org: $_"
    }
}
Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue

Decir ''
Decir '  [X] No se pudo conseguir Python automaticamente.'
foreach ($m in $motivos) { Decir "      - $m" }
Decir ''
if ($script:bloqueado) {
    Decir '      Python se bajo, pero Windows NO lo deja ejecutar desde la carpeta'
    Decir '      del usuario (AppLocker / control de aplicaciones de la empresa).'
    Decir '      Eso no se saltea desde aca, y no corresponde saltearlo: hace'
    Decir '      falta que IT instale Python 3.11 (Portal de Empresa / Software'
    Decir '      Center) o que habilite la carpeta python-runtime del paquete.'
} else {
    Decir '      Casi siempre es el proxy o el firewall de la empresa. Dos salidas:'
    Decir '      a) Pedir el paquete "con Python adentro" (carpeta python-runtime al'
    Decir '         lado del .bat): no descarga nada.'
    Decir '      b) Instalar Python 3.11 de https://www.python.org/downloads/ con'
    Decir '         "Add Python to PATH" (alcanza con "solo para mi usuario"), o'
    Decir '         pedirselo a IT desde el Portal de Empresa / Software Center.'
}
exit 1
