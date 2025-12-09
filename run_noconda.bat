@echo off
title Zeeman Slower App
echo Starting application...

:: 1. Verificar si el entorno está instalado
if not exist "ROA_DOZE" (
    echo [ERROR] Virtual environment not found.
    echo Please run 'install_noconda.bat' first.
    pause
    exit /b
)

:: 2. Activar el entorno virtual
call ROA_DOZE\Scripts\activate

:: 3. Ejecutar tu script principal
:: Asegurate de que ZeemanAPP.py esta en la misma carpeta que este .bat
python ZeemanAPP.py

:: 4. Si el programa falla, la ventana no se cierra inmediatamente
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The application crashed. See the error above.
    pause
)