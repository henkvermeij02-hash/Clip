@echo off
REM One-time setup for Windows. Double-click this file.
setlocal
cd /d "%~dp0"

echo.
echo ==^> Checking required programs
where python >nul 2>nul || (echo ERROR: Python is not installed or not on PATH. See README. & goto :fail)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" || (echo ERROR: Python 3.11 or newer is required. & goto :fail)
where node >nul 2>nul || (echo ERROR: Node.js is not installed. See README. & goto :fail)
where ffmpeg >nul 2>nul || (echo ERROR: FFmpeg is not on PATH. See README, or set its full path later on the Settings page. & goto :fail)

echo.
echo ==^> Installing backend (Python) packages
python -m venv backend\.venv || goto :fail
backend\.venv\Scripts\python -m pip install --upgrade pip -q
backend\.venv\Scripts\pip install -r backend\requirements.txt -q || goto :fail

echo.
echo ==^> Installing dashboard (Node.js) packages
pushd frontend
call npm install --no-fund --no-audit || (popd & goto :fail)
popd

echo.
echo Setup complete. Double-click start-windows.bat to start the studio.
pause
exit /b 0

:fail
echo.
echo Setup did not finish. Read the message above, fix it, then run this file again.
pause
exit /b 1
