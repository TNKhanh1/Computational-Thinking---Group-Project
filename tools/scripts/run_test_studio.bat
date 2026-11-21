@echo off
chcp 65001 >nul
title SmartSchedule - Verification Test Studio
cd /d "%~dp0\..\.."
set "PY_EXE=python"
if exist ".venv\Scripts\python.exe" set "PY_EXE=.venv\Scripts\python.exe"
"%PY_EXE%" tests\test_studio.py
if %ERRORLEVEL% NEQ 0 pause
