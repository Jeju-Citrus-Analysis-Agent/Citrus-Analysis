@echo off
cd /d "%~dp0.."
set "AGENT_PYTHON=python"
if exist "%~dp0..\.venv-agent\Scripts\python.exe" set "AGENT_PYTHON=%~dp0..\.venv-agent\Scripts\python.exe"
"%AGENT_PYTHON%" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
  echo Install dependencies first: python -m pip install -r citrus_freellm\requirements-ui.txt
  pause
  exit /b 1
)
"%AGENT_PYTHON%" -m streamlit run "%~dp0web.py" --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
if errorlevel 1 pause
