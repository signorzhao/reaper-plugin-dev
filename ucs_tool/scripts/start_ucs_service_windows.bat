@echo off
setlocal
cd /d "%~dp0"
set BASE_URL=http://127.0.0.1:8000
set UI_URL=%BASE_URL%/ui
set LOG_PATH=%~dp0enz_ucs_service.log

curl.exe -fsS --max-time 0.5 "%BASE_URL%/health" >nul 2>nul
if %errorlevel%==0 (
  start "" "%UI_URL%"
  exit /b 0
)

if exist "enz_ucs_service.exe" (
  start "ENZ UCS Service" /min "%~dp0enz_ucs_service.exe"
  goto wait_service
)
if exist "%~dp0..\.venv-ucs\Scripts\python.exe" (
  start "ENZ UCS Service" /min "%~dp0..\.venv-ucs\Scripts\python.exe" "%~dp0..\backend\ucs_service.py"
  goto wait_service
)
if exist "..\backend\ucs_service.py" (
  start "ENZ UCS Service" /min python "%~dp0..\backend\ucs_service.py"
  goto wait_service
)
echo enz_ucs_service.exe not found.
pause
exit /b 1

:wait_service
for /l %%i in (1,1,40) do (
  curl.exe -fsS --max-time 0.5 "%BASE_URL%/health" >nul 2>nul
  if not errorlevel 1 (
    start "" "%UI_URL%"
    exit /b 0
  )
  timeout /t 1 /nobreak >nul
)
echo Service did not respond in time. Log:
echo %LOG_PATH%
pause
exit /b 1
