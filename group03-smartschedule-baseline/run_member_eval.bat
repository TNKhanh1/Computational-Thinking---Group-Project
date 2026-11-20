@echo off
chcp 65001 >nul
echo ============================================================================
echo   SMARTSCHEDULE - MEMBER-IN-THE-LOOP BLIND EVALUATOR (PORT 8010)
echo   Course: CS252 - Computational Thinking (FIT-HCMUS)
echo   Team: Group 03 - The Seven Dwarfs
echo ============================================================================
echo.
cd /d "%~dp0"
set "PY_EXE=python"
if exist ".venv\Scripts\python.exe" set "PY_EXE=.venv\Scripts\python.exe"
echo Starting Blind Human-in-the-Loop Evaluator with %PY_EXE% at http://127.0.0.1:8010 ...
start "" http://127.0.0.1:8010
"%PY_EXE%" -B -m uvicorn member_eval.app:app --host 127.0.0.1 --port 8010 --reload
pause
