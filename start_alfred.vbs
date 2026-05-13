Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd ""C:\VS Code\JARVIS"" && .\venv\Scripts\python.exe web\app.py", 0, False
