@echo off
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-server.ps1"
if errorlevel 1 (
  echo Server could not start. See server-error.log in citrus_freellm.
  pause
  exit /b 1
)
python -m citrus_freellm
if errorlevel 1 pause
