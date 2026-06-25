@echo off
REM ===== Daily YouTube Shorts bot launcher (for Windows Task Scheduler) =====
cd /d "%~dp0"

REM Use the virtual environment if it exists, else system python
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" main.py
) else (
    python main.py
)
