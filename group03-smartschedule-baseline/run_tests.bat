@echo off
chcp 65001 >nul
echo ============================================================================
echo   SMARTSCHEDULE BASELINE (V0) - AUTOMATED PYTEST & BENCHMARK SUITE
echo   Course: CSC10014 - Computational Thinking (FIT-HCMUS)
echo   Team: Group 03 - The Seven Dwarfs
echo ============================================================================
echo.
cd /d "%~dp0"
echo [1/2] Running PyTest Unit & Scenario Suite (T01 - T10)...
python -m pytest -v
echo.
echo [2/2] Running Quantitative Benchmark Runner...
python benchmark_runner.py
pause

