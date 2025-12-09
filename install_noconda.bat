@echo off
title Installer - Zeeman Slower App
echo ==========================================
echo      INSTALLING DEPENDENCIES
echo ==========================================
echo.

:: 1. Comprobar si Python existe en el sistema
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python from python.org
    pause
    exit /b
)

:: 2. Crear entorno virtual "venv" si no existe
if not exist "ROA_DOZE" (
    echo [+] Creating virtual environment...
    python -m venv ROA_DOZE
) else (
    echo [i] Virtual environment already exists.
)

:: 3. Activar y actualizar pip
echo [+] Activating environment...
call ROA_DOZE\Scripts\activate

echo [+] Upgrading pip...
python -m pip install --upgrade pip

:: 4. Instalar librerias desde requirements.txt
if exist "requirements.txt" (
    echo [+] Installing libraries from requirements.txt...
    pip install -r requirements.txt
) else (
    echo [ERROR] requirements.txt not found!
    echo Please create the file with 'PyQt5' inside.
    pause
    exit /b
)

echo.
echo ==========================================
echo      INSTALLATION SUCCESSFUL
echo ==========================================
echo You can now run the application using run_noconda.bat
echo.
pause