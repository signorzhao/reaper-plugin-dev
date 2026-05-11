@echo off
setlocal
set BASE_URL=http://127.0.0.1:8000

curl.exe -fsS --max-time 1.0 -X POST "%BASE_URL%/api/v1/shutdown" >nul 2>nul
if %errorlevel%==0 (
  echo ENZ UCS service shutdown requested.
  exit /b 0
)

echo ENZ UCS service is not running, or it did not respond.
pause
exit /b 1
