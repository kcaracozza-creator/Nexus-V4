# Create desktop shortcut for NEXUS Dev Dashboard

$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "NEXUS Dev Dashboard.lnk"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "C:\Users\kcara\AppData\Local\Programs\Python\Python312\pythonw.exe"
$Shortcut.Arguments = "`"E:\NEXUS_V2_RECREATED\src\dev_dashboard.py`""
$Shortcut.WorkingDirectory = "E:\NEXUS_V2_RECREATED\src"
$Shortcut.IconLocation = "E:\NEXUS_V2_RECREATED\nexus_v2\assets\nexus.ico"
$Shortcut.Description = "NEXUS Development Dashboard - Multi-Agent System Monitor"
$Shortcut.Save()

Write-Host "Desktop shortcut created at: $ShortcutPath"
