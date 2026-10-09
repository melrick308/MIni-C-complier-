@echo off
rem Starts the MiniC Compiler Explorer at http://localhost:8000 (close this window to stop it).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Creating virtual environment and installing dependencies...
    python -m venv .venv || goto :error
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
)
echo MiniC Compiler Explorer running at http://localhost:8000  (Ctrl+C to stop)
start "" http://localhost:8000
.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 8000
goto :eof
:error
echo Setup failed. Make sure Python 3.11+ is installed and on PATH.
pause
