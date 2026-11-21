@echo off
chcp 65001 >nul
echo Starting Blind Human-in-the-Loop Evaluator at http://127.0.0.1:8010 ...
cd /d "%~dp0\..\.."
set "PY_EXE=python"
if exist ".venv\Scripts\python.exe" set "PY_EXE=.venv\Scripts\python.exe"
start "" http://127.0.0.1:8010
"%PY_EXE%" -B -m uvicorn tools.member_eval.app:app --host 127.0.0.1 --port 8010 --reload
pause
