@echo off
chcp 65001 >nul
echo Starting SmartSchedule Web Workbench at http://127.0.0.1:8000 ...
cd /d "%~dp0\..\.."
set "PY_EXE=python"
if exist ".venv\Scripts\python.exe" set "PY_EXE=.venv\Scripts\python.exe"
start "" http://127.0.0.1:8000
"%PY_EXE%" -m uvicorn smartschedule.api.app:app --host 127.0.0.1 --port 8000 --reload
pause
