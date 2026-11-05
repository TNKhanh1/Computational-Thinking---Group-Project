@echo off
chcp 65001 >nul
title SmartSchedule - Verification Test Suite Runner
cd /d "%~dp0\.."

python -B verification_tests\clean_runner.py %*

echo.
pause
