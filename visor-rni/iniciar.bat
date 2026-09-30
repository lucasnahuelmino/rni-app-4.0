@echo off
setlocal
cd /d "%~dp0"

rem ---------------------------------------------------------------------------
rem Visor RNI - servidor local.
rem
rem El visor usa modulos ES y carga el motor SQLite en WebAssembly; por eso
rem necesita http:// y no se puede abrir con doble clic en index.html.
rem Este archivo levanta un servidor estatico (sin instalar nada) y abre el
rem navegador. Puerto 8090 (el backend del proyecto RNI usa 8001).
rem
rem El texto de este archivo va sin tildes a proposito: si no, Windows puede
rem leerlo mal segun el codigo de pagina de la consola.
rem ---------------------------------------------------------------------------

set "PUERTO=8090"
set "URL=http://localhost:%PUERTO%/"
set "PY="
set "PYARGS="

where python >nul 2>nul
if not errorlevel 1 set "PY=python"

if not defined PY (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PY=py"
        set "PYARGS=-3"
    )
)

if not defined PY (
    if exist "%~dp0..\backend\.venv\Scripts\python.exe" set "PY=%~dp0..\backend\.venv\Scripts\python.exe"
)

if not defined PY (
    echo.
    echo   No encontre Python en el PATH.
    echo   Instalalo desde https://www.python.org/downloads/ y volvi a intentar,
    echo   o levanta el visor con cualquier servidor estatico (por ejemplo
    echo   "npx serve visor-rni") y abri el navegador en la direccion que te
    echo   diga. El contenido de la carpeta no cambia: solo se sirve por http.
    echo.
    pause
    exit /b 1
)

chcp 65001 >nul
echo.
echo   Visor RNI
echo   Servidor: %URL%
echo   Dejala abierta mientras la uses y cortala con la X de esta ventana.
echo.

start "" "%URL%"
"%PY%" %PYARGS% -m http.server %PUERTO%

echo.
echo   El servidor se cerro.
pause
