@echo off
chcp 65001 >nul
title SmartSchedule — Verification Test Suite Runner
cd /d "%~dp0\.."

echo ============================================================================
echo   SMARTSCHEDULE VERIFICATION TEST SUITE RUNNER
echo   Team 03 - The Seven Dwarfs - Builder 3 (Gia Bao)
echo ============================================================================
echo.

if "%1"=="" goto run_production
if "%1"=="--pass" goto run_production
if "%1"=="--all" goto run_all
if "%1"=="--ui" goto run_ui
if "%1"=="--arch" goto run_arch
if "%1"=="--logic" goto run_logic
if "%1"=="--bench" goto run_bench
if "%1"=="--edge" goto run_edge
if "%1"=="--gaps" goto run_gaps

:run_production
echo [*] Running Average Passing Tests (UI + Arch + Logic + Benchmarks)...
python -m pytest verification_tests/ui_tests verification_tests/architecture_tests/test_system_architecture.py verification_tests/architecture_tests/test_memory_leaks.py verification_tests/logical_tests/test_circular_dependencies.py verification_tests/logical_tests/test_undefined_behaviors.py verification_tests/logical_tests/test_generation.py verification_tests/benchmark_tests -v --tb=short
goto finish

:run_all
echo [*] Running Full 60/40 Test Matrix (Passing Average + Developmental Gaps)...
python -m pytest verification_tests -v --tb=short
goto finish

:run_edge
echo [*] Running 40%% Edge Cases & Failure Scenarios...
python -m pytest verification_tests/logical_tests/test_scheduling_edge_cases.py verification_tests/architecture_tests/test_production_failures.py verification_tests/benchmark_tests/test_feasibility_benchmarks.py -v --tb=short
goto finish

:run_gaps
echo [*] Running Improve Plan Target Feature Gap Tests (Expected Failures against V0)...
python -m pytest verification_tests/development_gap_tests/test_improve_plan_gaps.py -v --tb=short
goto finish

:run_ui
echo [*] Running UI & Endpoint Tests (verification_tests/ui_tests)...
python -m pytest verification_tests/ui_tests -v --tb=short
goto finish

:run_arch
echo [*] Running Architecture & Production Failure Tests...
python -m pytest verification_tests/architecture_tests -v --tb=short
goto finish

:run_logic
echo [*] Running Logical & Edge Case Tests...
python -m pytest verification_tests/logical_tests -v --tb=short
goto finish

:run_bench
echo [*] Running Benchmark Tests T01-T10 & Feasibility...
python -m pytest verification_tests/benchmark_tests -v --tb=short
goto finish

:finish
echo.
if %ERRORLEVEL% EQU 0 (
    echo ============================================================================
    echo   [SUCCESS] Targeted tests completed successfully!
    echo ============================================================================
) else (
    echo ============================================================================
    echo   [NOTICE] Test run completed. Review test output above for failures or gaps.
    echo ============================================================================
)
echo.
pause
