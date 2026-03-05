$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [Environment]::GetFolderPath('Desktop')

# Delete old V2 shortcut
$OldShortcut = "$Desktop\NEXUS V2.lnk"
if (Test-Path $OldShortcut) { Remove-Item $OldShortcut -Force; Write-Host "Removed old V2 shortcut" }

# Create V3 shortcut
$Shortcut = $WshShell.CreateShortcut("$Desktop\NEXUS V3.lnk")
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
$Shortcut.TargetPath = $PythonPath
$Shortcut.Arguments = "`"E:\NEXUS_V2_RECREATED\nexus_v2\main.py`""
$Shortcut.WorkingDirectory = "E:\NEXUS_V2_RECREATED"
$Shortcut.IconLocation = "E:\NEXUS_V2_RECREATED\nexus_v2\assets\nexus.ico,0"
$Shortcut.Description = "NEXUS V3 - Universal Collectibles System - Patent Pending - Kevin Caracozza"
$Shortcut.Save()

Write-Host "=== NEXUS V3 SHORTCUT CREATED ==="
Write-Host "Location: $Desktop\NEXUS V3.lnk"
