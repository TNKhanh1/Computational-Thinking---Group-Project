@echo off
chcp 65001 >nul
title SmartSchedule - Automated Environment Setup
cd /d "%~dp0\..\.."

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python was not found in your system PATH!
    pause
    exit /b 1
)

if not exist ".venv" (
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r environments\requirements.txt
if %ERRORLEVEL% NEQ 0 (
    pause
    exit /b 1
)

echo [SUCCESS] Environment setup complete!
echo Quick commands:
echo   - Run Web Workbench:     tools\scripts\run_app.bat
echo   - Run Test Studio:       tools\scripts\run_test_studio.bat
echo   - Run Verification:      tools\scripts\run_verification_tests.bat --pass
pause
