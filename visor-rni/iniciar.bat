@echo off
setlocal
cd /d "%~dp0"

rem ---------------------------------------------------------------------------
rem Visor RNI - servidor local, sin instalar nada.
rem
rem El visor usa modulos ES y carga el motor SQLite en WebAssembly; por eso
rem necesita http:// y no se puede abrir con doble clic en index.html.
rem Este archivo levanta servidor.ps1 (PowerShell, que ya viene con Windows
rem 10 o superior) y abre el navegador. Puerto 8090 (el backend del proyecto
rem RNI usa 8001).
rem
rem El texto de este archivo va sin tildes a proposito: si no, Windows puede
rem leerlo mal segun el codigo de pagina de la consola.
rem ---------------------------------------------------------------------------

where powershell >nul 2>nul
if errorlevel 1 (
    echo.
    echo   No encontre PowerShell. Viene con Windows 10 o superior.
    echo   Como alternativa, cualquier servidor estatico sirve, por ejemplo
    echo   "npx serve visor-rni": el contenido de la carpeta no cambia,
    echo   solo se sirve por http.
    echo.
    pause
    exit /b 1
)

chcp 65001 >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0servidor.ps1"

echo.
echo   El servidor se cerro.
pause
