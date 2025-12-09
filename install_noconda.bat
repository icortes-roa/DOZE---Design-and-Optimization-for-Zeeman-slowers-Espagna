@echo off
title Installer - Zeeman Slower App
echo ==========================================
echo      INSTALLING DEPENDENCIES
echo ==========================================
echo.

:: 1. Check if python exist in system PATH
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python from python.org
    pause
    exit /b
)

:: 2. Create virtual environment "ROA_DOZE"
if not exist "ROA_DOZE" (
    echo [+] Creating virtual environment...
    python -m venv ROA_DOZE
) else (
    echo [i] Virtual environment already exists.
)

:: 3. Environment activation and pip upgrading
echo [+] Activating environment...
call ROA_DOZE\Scripts\activate

echo [+] Upgrading pip...
python -m pip install --upgrade pip

:: 4. Installing libraries from requirements.txt
if exist "requirements.txt" (
    echo [+] Installing libraries from requirements.txt...
    pip install -r requirements.txt
) else (
    echo [ERROR] requirements.txt not found!
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