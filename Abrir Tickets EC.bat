@echo off
REM ===========================================================================
REM  Tickets - Excelencia Comercial y Digital: arranque con doble clic
REM
REM  No instala nada en el sistema ni pide administrador. Todo vive en
REM  %LOCALAPPDATA%\Tickets EC y se puede borrar a mano.
REM
REM  Mismo patron que Adium_AllinOne.bat de la suite, con sus dos trampas de
REM  cmd.exe resueltas: adentro de un bloque la ruta va con !AQUI! y no con
REM  %~dp0, y los REM de adentro de un bloque no llevan comillas ni parentesis.
REM  Ante cualquier error la ventana NO se cierra: dice que paso y espera.
REM  Hay un test que vigila todo esto: tests/test_lanzador.py.
REM ===========================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"
title Tickets - Excelencia Comercial y Digital
set "AQUI=%~dp0"

if not exist "%AQUI%app\app.py" (
    echo.
    echo  [X] No encuentro la app junto a este archivo.
    echo      Este .bat tiene que quedar en la carpeta del repositorio,
    echo      al lado de las carpetas app y tickets_ec.
    echo.
    pause
    exit /b 1
)

REM --- 1. Python -------------------------------------------------------------
REM  packaging\conseguir_python.ps1, el mismo de la suite: busca un Python
REM  3.11 a 3.13 y, si no hay, baja el oficial a la carpeta del usuario, sin
REM  administrador. Va FUERA de todo bloque: el for /f lleva parentesis.
set "BASE=%LOCALAPPDATA%\Tickets EC"
set "ADIUM_BASE=%BASE%"
set "ADIUM_LOG=%BASE%\conseguir_python.log"
set "PYERR=%BASE%\conseguir_python.err"
if not exist "%BASE%\." mkdir "%BASE%"
if exist "%ADIUM_LOG%" del /q "%ADIUM_LOG%"
if exist "%PYERR%" del /q "%PYERR%"
set "ADIUM_PS1=%AQUI%packaging\conseguir_python.ps1"
set "ADIUM_RUNTIME_LOCAL="
if exist "%AQUI%python-runtime\." set "ADIUM_RUNTIME_LOCAL=%AQUI%python-runtime"
set "PYTIPO="
set "PYEXE="

REM  Primero lo que no necesita PowerShell. Un Python propio de esta mesa
REM  ya bajado antes, o el python-runtime del paquete, se usan tal cual: el
REM  de nuget no trae venv. El que bajo la suite Adium All in One se usa
REM  como base de un venv aparte, para no tocarle sus librerias.
set "CAND=%AQUI%python-runtime\python.exe"
if not exist "%CAND%" set "CAND=%BASE%\python\tools\python.exe"
if exist "%CAND%" "%CAND%" -c "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)" >nul 2>&1 && "%CAND%" -m pip --version >nul 2>&1 && set "PYTIPO=propio" && set "PYEXE=%CAND%"
if defined PYEXE goto :python_listo
set "CAND=%LOCALAPPDATA%\Adium All in One\python\tools\python.exe"
if exist "%CAND%" "%CAND%" -c "import sys, venv; sys.exit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)" >nul 2>&1 && set "PYTIPO=sistema" && set "PYEXE=%CAND%"
if defined PYEXE goto :python_listo

echo   Buscando Python ^(si no hay, se baja uno; la primera vez tarda unos minutos^)...
for /f "tokens=1,* delims=|" %%A in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "iex (Get-Content -Raw -LiteralPath $env:ADIUM_PS1)" 2^>"%PYERR%"') do (
    set "PYTIPO=%%A"
    set "PYEXE=%%B"
)
if exist "%ADIUM_LOG%" type "%ADIUM_LOG%"

:python_listo
if not defined PYEXE (
    echo.
    echo  ============================================================
    echo   No se pudo conseguir Python automaticamente
    echo  ============================================================
    echo.
    if exist "!PYERR!" type "!PYERR!"
    echo   Pedile a IT Python 3.11, 3.12 o 3.13 desde el Portal de Empresa
    echo   o Software Center, y volve a abrir este archivo.
    echo   El detalle queda en: !ADIUM_LOG!
    echo.
    pause
    exit /b 1
)

REM --- 2. Entorno propio, en la carpeta del usuario -------------------------
set "VENV=%BASE%\venv"
if /i "%PYTIPO%"=="propio" (
    set "PYW=!PYEXE!"
    goto :entorno_listo
)
if exist "%VENV%\Scripts\python.exe" (
    "%VENV%\Scripts\python.exe" -c "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo   El entorno anterior es de otra version de Python: se rehace.
        rmdir /s /q "%VENV%"
    )
)
if not exist "%VENV%\Scripts\python.exe" (
    echo.
    echo   Preparando el entorno por unica vez. Tarda un par de minutos.
    "!PYEXE!" -m venv "%VENV%"
    if errorlevel 1 (
        echo.
        echo  [X] No se pudo crear el entorno en "%VENV%".
        echo.
        pause
        exit /b 1
    )
)
set "PYW=%VENV%\Scripts\python.exe"

:entorno_listo

REM --- 3. Dependencias --------------------------------------------------------
REM  Se instala si falta algo o si la version de Streamlit es vieja. Asi un
REM  Streamlit de antes no hace caer la app con un TypeError al abrir.
"%PYW%" -c "import streamlit, pandas, openpyxl, msal; v = tuple(int(x) for x in streamlit.__version__.split('.')[:2]); raise SystemExit(0 if v >= (1, 50) else 1)" >nul 2>&1
if errorlevel 1 (
    echo   Instalando lo que necesita la app...
    if exist "!AQUI!ruedas\." (
        echo   ^(carpeta ruedas encontrada: se instala sin salir a internet^)
        set FUENTE=--no-index --find-links "!AQUI!ruedas"
    ) else (
        "%PYW%" -m pip install --upgrade pip --quiet >nul 2>&1
        set FUENTE=
    )
    "%PYW%" -m pip install !FUENTE! -r "!AQUI!requirements-app.txt" --quiet
    if errorlevel 1 (
        echo.
        echo  [X] Fallo la instalacion de dependencias.
        echo.
        echo      Casi siempre es el proxy de la empresa. Para ver el motivo
        echo      real, corre esto en una consola:
        echo        "%PYW%" -m pip install -r "!AQUI!requirements-app.txt"
        echo.
        echo      Sin salida a PyPI: en una maquina con internet se arma una
        echo      vez la carpeta ruedas y se copia al lado de este .bat:
        echo        pip wheel -r requirements-app.txt -w ruedas
        echo.
        pause
        exit /b 1
    )
)

REM --- 4. La primera vez: la mesa vacia o la demo -----------------------------
if not exist "%AQUI%datos\tickets.db" (
    echo.
    echo   La mesa esta vacia. La demo son 18 meses de pedidos ficticios,
    echo   para recorrer la app y el tablero. Tarda unos 30 segundos.
    choice /C SN /M "  Cargar la demo"
    if errorlevel 2 (
        echo   Sin demo: la mesa arranca vacia.
    ) else (
        "%PYW%" -m tickets_ec.demo
        if errorlevel 1 (
            echo  [!] La demo no se pudo cargar. La app abre igual, vacia.
            pause
        )
    )
)

REM --- 5. Abrir ---------------------------------------------------------------
REM  El puerto y la direccion salen de .streamlit\config.toml: 8750, solo
REM  esta PC. Si ya habia una mesa abierta, se abre el navegador sobre esa.
set "STREAMLIT_SERVER_HEADLESS=false"
"%PYW%" -c "import socket; s = socket.socket(); s.settimeout(1); raise SystemExit(0 if s.connect_ex(('127.0.0.1', 8750)) == 0 else 1)" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo   La mesa ya estaba abierta: abro el navegador.
    start "" http://localhost:8750
    timeout /t 3 >nul
    exit /b 0
)

echo.
echo  ============================================================
echo   Tickets - Excelencia Comercial y Digital
echo   Abriendo en  http://localhost:8750
echo   Para cerrar la mesa: cerra esta ventana negra.
echo  ============================================================
echo.
"%PYW%" -m streamlit run "%AQUI%app\app.py"

if errorlevel 1 (
    echo.
    echo  [X] La app termino con error. Las lineas de arriba dicen por que.
    echo.
    pause
)
endlocal
