@echo off
chcp 65001 >nul
echo ========================================
echo   MegaDetector - Instalador Windows
echo ========================================
echo.

echo [1/3] Verificando Docker Desktop...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Docker Desktop no esta instalado
    echo.
    echo Descarga Docker Desktop desde:
    echo https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

echo [OK] Docker Desktop encontrado
echo.

echo [2/3] Construyendo contenedor...
docker-compose build

echo.
echo [3/3] Iniciando MegaDetector...
docker-compose up -d

echo.
echo ========================================
echo   Instalacion completa!
echo ========================================
echo.
echo Abre tu navegador en: http://localhost:8501
echo.
echo Comandos utiles:
echo   docker-compose down    (detener)
echo   docker-compose logs -f (ver logs)
echo.
pause
