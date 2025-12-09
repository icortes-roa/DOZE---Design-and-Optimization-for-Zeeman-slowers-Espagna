@echo off
title Zeeman Slower App Launcher
set ENV_NAME=ROA_DOZE

echo --- SEARCHING FOR CONDA ---

:: -------------------------------------------------------
:: PHASE 1: Locate Anaconda/Miniconda
:: -------------------------------------------------------

set "ACTIVATE_PATH="

:: Look for activate.bat in common installation paths
if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" set "ACTIVATE_PATH=%USERPROFILE%\anaconda3\Scripts\activate.bat"
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" set "ACTIVATE_PATH=%USERPROFILE%\miniconda3\Scripts\activate.bat"
if exist "C:\ProgramData\Anaconda3\Scripts\activate.bat" set "ACTIVATE_PATH=C:\ProgramData\Anaconda3\Scripts\activate.bat"
if exist "C:\Anaconda3\Scripts\activate.bat" set "ACTIVATE_PATH=C:\Anaconda3\Scripts\activate.bat"

:: If not found in common paths, check the system PATH
if not defined ACTIVATE_PATH (
    where conda >nul 2>&1
    if %errorlevel% equ 0 (
        echo [i] Conda detected in global PATH.
        :: Assume we can call activate directly if it's in the path
        set "ACTIVATE_PATH=activate"
    )
)

if not defined ACTIVATE_PATH (
    echo [ERROR] Could not automatically find Anaconda or Miniconda.
    echo Please verify your installation.
    pause
    exit /b
)

:: -------------------------------------------------------
:: PHASE 2: Activate Environment Directly
:: -------------------------------------------------------

echo.
echo --- Activating Environment: %ENV_NAME% ---
echo [i] Using activation script: "%ACTIVATE_PATH%"

:: THIS IS THE FIX: Call activate.bat and pass the environment name
call "%ACTIVATE_PATH%" %ENV_NAME%

:: Visual verification (Look for the * next to your env name)
echo.
echo Current Environment:
conda info --envs | findstr "*"

:: -------------------------------------------------------
:: PHASE 3: Run the App
:: -------------------------------------------------------
echo.
echo --- Running Application ---

:: Run Python. Since the env is active, this uses the Python from ROA_DOZE
python "ZeemanAPP.py"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The application crashed.
    echo Please check if libraries (e.g., PyQt5) are installed in %ENV_NAME%.
    pause
)
:: -------------------------------------------------------
::