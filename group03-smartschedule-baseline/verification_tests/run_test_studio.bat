@echo off
chcp 65001 >nul
title SmartSchedule - Verification Test Studio
cd /d "%~dp0"

set "PY_EXE=python"
if exist "..\.venv\Scripts\python.exe" set "PY_EXE=..\.venv\Scripts\python.exe"

echo ============================================================================
echo   SMARTSCHEDULE VERIFICATION TEST STUDIO
echo   Role: Builder 3 - System Architecture & Pre-deployment Testing
echo ============================================================================
echo.
echo Launching Verification Studio window (%PY_EXE%)...
"%PY_EXE%" test_studio.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Verification Studio exited with error: %ERRORLEVEL%
    pause
)

