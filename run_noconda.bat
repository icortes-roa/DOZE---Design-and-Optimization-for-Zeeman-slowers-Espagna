@echo off
title Zeeman Slower App
echo Starting application...

:: 1. We check the environment "ROA_DOZE" is present
if not exist "ROA_DOZE" (
    echo [ERROR] Virtual environment not found.
    echo Please run 'install_noconda.bat' first.
    pause
    exit /b
)

:: 2. We activate virtual environment "ROA_DOZE"
call ROA_DOZE\Scripts\activate

:: 3. Main script execution
:: Be sure ZeemanAPP.py in in the same folder this bat is
python ZeemanAPP.py

:: 4. If execution fails, window is not closed inmediately
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The application crashed. See the error above.
    pause
)