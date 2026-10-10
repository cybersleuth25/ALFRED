@echo off
echo Building new V3 UI...
cd /d "%~dp0frontend"
call npm run build
echo Build complete! You can now start Alfred.
pause
