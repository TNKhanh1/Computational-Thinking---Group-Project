@echo off
chcp 65001 >nul
echo ============================================================================
echo   SMARTSCHEDULE BASELINE (V0) - TECHNICAL BENCHMARK WORKBENCH
echo   Course: CSC10014 - Computational Thinking (FIT-HCMUS)
echo   Team: Group 03 - The Seven Dwarfs
echo ============================================================================
echo.
cd /d "%~dp0"
echo Starting FastAPI Web Workbench at http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000
python -m uvicorn web.api:app --host 127.0.0.1 --port 8000 --reload
pause

