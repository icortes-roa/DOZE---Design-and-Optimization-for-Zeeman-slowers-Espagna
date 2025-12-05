@echo off
echo --- Creating Conda Environment ---

:: Check if Conda is available
conda --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Conda is not found. Please open this file using Anaconda Prompt.
    pause
    exit /b
)

:: Create environment from YAML file
echo Creating environment from ROA_DOZE.yml...
call conda env create -f ROA_DOZE.yml

echo.
echo --- Installation Finished ---
pause