@echo off
:: Alfred Protocol - Windows Startup Launcher
:: This script starts Alfred silently when Windows boots up.
:: Place a shortcut to this file in: shell:startup

cd /d "C:\VS code\JARVIS"

:: Start Alfred backend + frontend in a hidden window
start /min "" pythonw web\app.py

:: If pythonw is not available, fall back to python with hidden console
if %ERRORLEVEL% NEQ 0 (
    start /min "" python web\app.py
)
