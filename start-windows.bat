@echo off
REM Starts GTA Shorts AI Studio. Double-click this file. Close the two windows to stop.
cd /d "%~dp0"
if not exist backend\.venv\Scripts\uvicorn.exe (echo Run setup-windows.bat first. & pause & exit /b 1)
if not exist frontend\node_modules (echo Run setup-windows.bat first. & pause & exit /b 1)

start "GTA Studio - backend (keep open)" cmd /k "cd /d %~dp0backend && .venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "GTA Studio - dashboard (keep open)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo Starting... your browser will open in a few seconds.
timeout /t 8 /nobreak >nul
start "" http://localhost:3000
