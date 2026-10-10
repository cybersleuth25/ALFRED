$RepoDir = $PSScriptRoot
$WshShell = New-Object -ComObject WScript.Shell
$StartupPath = [System.IO.Path]::Combine($env:APPDATA, "Microsoft\Windows\Start Menu\Programs\Startup\Alfred Protocol.lnk")
$Shortcut = $WshShell.CreateShortcut($StartupPath)
$Shortcut.TargetPath = Join-Path $RepoDir "start_alfred.bat"
$Shortcut.WorkingDirectory = $RepoDir
$Shortcut.WindowStyle = 7
$Shortcut.Description = "Alfred AI Assistant"
$Shortcut.Save()
Write-Host "Startup shortcut created at: $StartupPath"
