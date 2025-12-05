@echo off
echo --- Starting the Application ---

:: 1. Check if the environment exists
if not exist "DOZE_ROA" (
    echo Error: Virtual environment not found. Please run install_noconda.bat first.
    pause
    exit /b
)

:: 2. Activate environment
call ROA_DOZE\Scripts\activate

:: 3. Run the main script
echo Running script...
python ZeemanAPP.py

:: 4. Cleanup
call deactivate
pause