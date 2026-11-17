@echo off
chcp 65001 >nul
echo ============================================================================
echo   SMARTSCHEDULE BASELINE (V0) - TECHNICAL BENCHMARK WORKBENCH
echo   Course: CSC10014 - Computational Thinking (FIT-HCMUS)
echo   Team: Group 03 - The Seven Dwarfs
echo ============================================================================
echo.
cd /d "%~dp0"
set "PY_EXE=python"
if exist ".venv\Scripts\python.exe" set "PY_EXE=.venv\Scripts\python.exe"
echo Starting FastAPI Web Workbench with %PY_EXE% at http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000
"%PY_EXE%" -m uvicorn web.api:app --host 127.0.0.1 --port 8000 --reload
pause

