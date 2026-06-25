@echo off
REM ===== One-time YouTube authorization =====
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" authorize.py
) else (
    python authorize.py
)
echo.
pause
