@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  start "" /min py -3 "%~dp0main.py"
  exit /b 0
)
where python >nul 2>&1
if %errorlevel%==0 (
  start "" /min python "%~dp0main.py"
  exit /b 0
)
echo Python bulunamadi. Python yukleyin veya PATH'e ekleyin.
echo Sonra: py -m pip install -r requirements.txt
pause
exit /b 1
