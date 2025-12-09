@echo off
title Installer - Zeeman Slower App (Conda Auto-Detect)
echo ==========================================
echo      SEARCHING FOR CONDA INSTALLATION
echo ==========================================
echo.

:: -------------------------------------------------------
:: PHASE 1: Try to find Conda and activate it
:: -------------------------------------------------------

:: 1. Check if Conda is already in PATH (Best case)
call conda --version >nul 2>&1
if %errorlevel% equ 0 goto :FOUND_CONDA

:: 2. If not in PATH, search in common default locations
echo [i] Conda not in PATH. Searching default folders...

set "CONDA_PATH="

:: Check common paths for Anaconda and Miniconda
if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" set "CONDA_PATH=%USERPROFILE%\anaconda3"
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" set "CONDA_PATH=%USERPROFILE%\miniconda3"
if exist "C:\ProgramData\Anaconda3\Scripts\activate.bat" set "CONDA_PATH=C:\ProgramData\Anaconda3"
if exist "C:\Anaconda3\Scripts\activate.bat" set "CONDA_PATH=C:\Anaconda3"

:: If we found a path, activate it
if defined CONDA_PATH (
    echo [i] Found Conda at: %CONDA_PATH%
    call "%CONDA_PATH%\Scripts\activate.bat"
    goto :FOUND_CONDA
)

:: 3. If everything fails
echo.
echo [ERROR] Could not find Anaconda automatically.
echo ---------------------------------------------------
echo Please open "Anaconda Prompt" from the Start Menu,
echo navigate to this folder, and run this file again.
echo ---------------------------------------------------
pause
exit /b

:: -------------------------------------------------------
:: PHASE 2: Run the Installation
:: -------------------------------------------------------
:FOUND_CONDA
echo [OK] Conda detected!
echo.
echo ==========================================
echo      CREATING CONDA ENVIRONMENT
echo ==========================================

:: Check if environment exists
call conda env list | findstr "ROA_DOZE" >nul
if %errorlevel% equ 0 (
    echo [i] Environment 'ROA_DOZE' already exists.
    echo     Updating...
    call conda env update -f ROA_DOZE.yml --prune
) else (
    echo [+] Creating new environment...
    call conda env create -f ROA_DOZE.yml
)

echo.
echo ==========================================
echo      INSTALLATION FINISHED
echo ==========================================
echo You can close this window.
pause