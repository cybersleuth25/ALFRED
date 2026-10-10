@echo off
"%~dp0venv\Scripts\pip.exe" install numpy geopy --upgrade
"%~dp0venv\Scripts\pip.exe" install torchvision==0.21.0
