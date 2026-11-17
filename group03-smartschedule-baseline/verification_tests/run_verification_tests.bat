@echo off
chcp 65001 >nul
title SmartSchedule - Verification Test Suite Runner
cd /d "%~dp0\.."

set "PY_EXE=python"
if exist ".venv\Scripts\python.exe" set "PY_EXE=.venv\Scripts\python.exe"
"%PY_EXE%" -B verification_tests\clean_runner.py %*

echo.
pause
