@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating ParkCare virtual environment...
  python -m venv --without-pip .venv
  if errorlevel 1 goto failed
)
echo Checking and installing required packages...
python -m pip --python .venv install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Starting ParkCare at http://127.0.0.1:5000
echo Keep this window open while using ParkCare. Press Ctrl+C to stop it.
".venv\Scripts\python.exe" -m flask --app app run
if errorlevel 1 goto failed
goto end
:failed
echo.
echo ParkCare could not start. Install Python 3 and make sure 'python' is available on PATH.
pause
:end
endlocal
