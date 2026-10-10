@echo off
:: Alfred notch - Coucou-style island at the top-centre of the screen.
:: Hover the top edge to peek, click to open, Esc to fold.
cd /d "%~dp0"
set "PYW=pythonw"
if exist "venv\Scripts\pythonw.exe" set "PYW=venv\Scripts\pythonw.exe"
start "" %PYW% desktop_island.py
