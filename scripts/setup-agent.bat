@echo off
REM Navigate to the agent directory
cd /d "%~dp0\..\agent" || exit /b 1

REM Replace 'uv sync' with the correct command if needed
REM Example: pip install uv
python -m uv sync