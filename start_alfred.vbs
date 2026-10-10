Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
repoDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = repoDir
WshShell.Run """" & repoDir & "\venv\Scripts\python.exe"" web\app.py", 0, False
