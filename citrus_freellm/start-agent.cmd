@echo off
cd /d "%~dp0.."
set "AGENT_PYTHON=python"
if exist "%~dp0..\.venv-agent\Scripts\python.exe" set "AGENT_PYTHON=%~dp0..\.venv-agent\Scripts\python.exe"
"%AGENT_PYTHON%" -m citrus_freellm %*
if errorlevel 1 pause
