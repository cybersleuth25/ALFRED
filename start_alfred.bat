@echo off
:: Alfred Protocol - Windows Startup Launcher
:: This script starts Alfred silently when Windows boots up.
:: Place a shortcut to this file in: shell:startup

:: Run from the folder this script lives in (works wherever the repo is cloned)
cd /d "%~dp0"

:: Prefer the project venv if present
set "PYW=pythonw"
set "PY=python"
if exist "venv\Scripts\pythonw.exe" set "PYW=venv\Scripts\pythonw.exe"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"

:: Start Alfred backend + frontend in a hidden window
start /min "" %PYW% web\app.py

:: If pythonw is not available, fall back to python with hidden console
if %ERRORLEVEL% NEQ 0 (
    start /min "" %PY% web\app.py
)
