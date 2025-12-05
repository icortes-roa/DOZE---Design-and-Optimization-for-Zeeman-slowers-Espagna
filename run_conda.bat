@echo off
echo --- Starting the Application ---

set ENV_NAME=ROA_DOZE

:: Activate Conda environment
:: We use 'call conda' to ensure the batch script continues after activation
call conda activate %ROA_DOZE%

if %errorlevel% neq 0 (
    echo Error: Could not activate environment '%ROA_DOZE%'.
    pause
    exit /b
)

:: Run the script
python ZeemanAPP.py

pause