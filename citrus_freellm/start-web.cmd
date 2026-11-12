@echo off
cd /d "%~dp0.."
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
  echo Install dependencies first: python -m pip install -r citrus_freellm\requirements-ui.txt
  pause
  exit /b 1
)
if exist "%~dp0runtime\server\dist\index.js" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-server.ps1"
  if errorlevel 1 echo Model server unavailable. Local explanations and scenarios are still available.
) else (
  echo FreeLLMAPI runtime is not installed. Local explanations and scenarios are available.
)
python -m streamlit run "%~dp0web.py" --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
if errorlevel 1 pause
