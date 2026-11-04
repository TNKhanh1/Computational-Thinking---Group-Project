@echo off
chcp 65001 >nul
title SmartSchedule - Automated Environment Setup
cd /d "%~dp0"

echo ============================================================================
echo   SMARTSCHEDULE - AUTOMATED ENVIRONMENT SETUP
echo   Group 03 - The Seven Dwarfs - FIT-HCMUS
echo ============================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python was not found in your system PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

echo [*] Python detected:
python --version
echo.

if not exist ".venv" (
    echo [*] Creating isolated virtual environment (.venv)...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully.
) else (
    echo [OK] Existing virtual environment found in .venv.
)
echo.

echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [*] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [*] Installing requirements from requirements.txt...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo   [SUCCESS] Environment setup complete!
echo ============================================================================
echo.
echo Quick commands:
echo   - Run Web Workbench:     python -m uvicorn web.api:app --host 127.0.0.1 --port 8000
echo   - Run Test Studio:       verification_tests\run_test_studio.bat
echo   - Run Passing Tests:     verification_tests\run_verification_tests.bat --pass
echo.
pause

