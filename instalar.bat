@echo off
chcp 65001 >nul
title MegaDetector - Instalador

echo ========================================
echo   MegaDetector - Detector de Fauna
echo   Sinergia Ambiental
echo ========================================
echo.

:: Verificar Docker
echo [Paso 1/4] Verificando Docker Desktop...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [X] Docker Desktop NO esta instalado
    echo.
    echo Por favor:
    echo 1. Descarga Docker Desktop:
    echo    https://www.docker.com/products/docker-desktop/
    echo 2. Instalalo
    echo 3. Reinicia tu computadora
    echo 4. Ejecuta este archivo de nuevo
    echo.
    pause
    exit /b 1
)
echo [OK] Docker Desktop instalado
echo.

:: Verificar que Docker esté corriendo
echo [Paso 2/4] Verificando que Docker este activo...
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [!] Docker Desktop no esta corriendo
    echo.
    echo Por favor:
    echo 1. Abre Docker Desktop (icono de ballena)
    echo 2. Espera 30 segundos a que inicie
    echo 3. Ejecuta este archivo de nuevo
    echo.
    pause
    exit /b 1
)
echo [OK] Docker Desktop activo
echo.

:: Construir contenedor
echo [Paso 3/4] Preparando MegaDetector (esto puede tardar 5-10 minutos)...
docker-compose build
if %errorlevel% neq 0 (
    echo.
    echo [X] Error al construir contenedor
    echo Verifica tu conexion a internet
    echo.
    pause
    exit /b 1
)
echo [OK] Contenedor listo
echo.

:: Iniciar contenedor
echo [Paso 4/4] Iniciando MegaDetector...
docker-compose up -d
if %errorlevel% neq 0 (
    echo [X] Error al iniciar
    pause
    exit /b 1
)

echo.
echo ========================================
echo   [EXITO] MegaDetector esta listo!
echo ========================================
echo.
echo La aplicacion esta corriendo en:
echo.
echo    http://localhost:8501
echo.
echo Abre esa direccion en tu navegador.
echo.
echo NOTA: La primera vez tarda 2-3 minutos
echo       en descargar el modelo (100 MB)
echo.
echo ---------------------------
echo Comandos utiles:
echo   docker-compose down       Detener
echo   docker-compose logs -f    Ver actividad
echo   docker-compose restart    Reiniciar
echo ---------------------------
echo.

:: Intentar abrir navegador automáticamente
echo Abriendo navegador...
timeout /t 3 >nul
start http://localhost:8501

echo.
pause
