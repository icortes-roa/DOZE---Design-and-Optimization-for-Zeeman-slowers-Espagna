@echo off
echo --- Starting Installation ---

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not added to the system PATH.
    pause
    exit /b
)

:: 2. Create virtual environment named "DOZE_ROA" if it doesn't exist
if not exist "DOZE_ROA" (
    echo Creating virtual environment...
    python -m venv DOZE_ROA
)

:: 3. Activate environment and install libraries
echo Installing dependencies from requirements.txt...
call DOZE_ROA\Scripts\activate
pip install -r requirements.txt

echo.
echo --- Installation completed successfully ---
pause