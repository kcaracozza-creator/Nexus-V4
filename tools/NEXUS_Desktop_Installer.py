#!/usr/bin/env python3
"""
NEXUS Desktop Application Installer
Creates deployable package for Windows PCs
"""
import os
import sys
import shutil
import zipfile
import json
from pathlib import Path

class NexusDesktopPackager:
    def __init__(self):
        self.source_dir = Path(os.getcwd())
        self.package_name = "NEXUS_Desktop_v2"
        self.output_dir = self.source_dir / "deployments" / "desktop"
        
    def create_package(self):
        """Create complete desktop deployment package"""
        print("🚀 Creating NEXUS Desktop Deployment Package...")
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        package_dir = self.output_dir / self.package_name
        
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir()
        
        # Core application files
        core_files = [
            "nexus_ULTIMATE.py",      # Main application
            "nexus_COMPLETE.py",      # Backup version
            "nexus.py",               # Core version
            "requirements.txt",       # Dependencies
        ]
        
        # Essential directories
        essential_dirs = [
            "config",
            "data/library", 
            "assets",
            "tools",
            "scripts"
        ]
        
        # Copy core files
        print("📁 Copying core application files...")
        for file in core_files:
            if (self.source_dir / file).exists():
                shutil.copy2(self.source_dir / file, package_dir / file)
                print(f"  ✅ {file}")
        
        # Copy essential directories
        print("📂 Copying essential directories...")
        for dir_name in essential_dirs:
            src_dir = self.source_dir / dir_name
            if src_dir.exists():
                dst_dir = package_dir / dir_name
                shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
                print(f"  ✅ {dir_name}/")
        
        # Create Windows installer batch file
        self.create_windows_installer(package_dir)
        
        # Create launcher script
        self.create_launcher(package_dir)
        
        # Create deployment instructions
        self.create_instructions(package_dir)
        
        # Create ZIP package
        zip_path = self.output_dir / f"{self.package_name}.zip"
        self.create_zip(package_dir, zip_path)
        
        print(f"\n🎉 NEXUS Desktop Package Created!")
        print(f"📦 Package: {zip_path}")
        print(f"📁 Size: {self.get_size_mb(zip_path):.1f} MB")
        
        return zip_path
    
    def create_windows_installer(self, package_dir):
        """Create Windows installer batch file"""
        installer_content = '''@echo off
echo ================================================================
echo                    NEXUS DESKTOP INSTALLER
echo ================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found! Please install Python 3.9+ first.
    echo Download from: https://python.org/downloads
    pause
    exit /b 1
)

echo ✅ Python found
echo.

REM Create NEXUS directory
set NEXUS_DIR=%USERPROFILE%\\NEXUS
echo 📁 Installing to: %NEXUS_DIR%
if not exist "%NEXUS_DIR%" mkdir "%NEXUS_DIR%"

REM Copy files
echo 📂 Copying NEXUS files...
xcopy /s /e /y "%~dp0*" "%NEXUS_DIR%\\" >nul

REM Install Python dependencies
echo 📦 Installing Python dependencies...
cd /d "%NEXUS_DIR%"
python -m pip install --user -r requirements.txt

REM Create desktop shortcut
echo 🖥️  Creating desktop shortcut...
set DESKTOP=%USERPROFILE%\\Desktop
set SHORTCUT=%DESKTOP%\\NEXUS.lnk
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT%'); $Shortcut.TargetPath = 'python'; $Shortcut.Arguments = '%NEXUS_DIR%\\launch_nexus.py'; $Shortcut.WorkingDirectory = '%NEXUS_DIR%'; $Shortcut.IconLocation = '%NEXUS_DIR%\\nexus_icon.ico'; $Shortcut.Save()"

echo.
echo ✅ NEXUS Desktop Installation Complete!
echo.
echo 🚀 Launch NEXUS:
echo    - Double-click "NEXUS" shortcut on desktop
echo    - Or run: python "%NEXUS_DIR%\\launch_nexus.py"
echo.
pause
'''
        
        installer_path = package_dir / "Install_NEXUS_Desktop.bat"
        with open(installer_path, 'w', encoding='utf-8') as f:
            f.write(installer_content)
        
        print("  ✅ Install_NEXUS_Desktop.bat")
    
    def create_launcher(self, package_dir):
        """Create Python launcher script"""
        launcher_content = '''#!/usr/bin/env python3
"""
NEXUS Desktop Launcher
Starts the main NEXUS application with error handling
"""
import sys
import os
import tkinter as tk
from tkinter import messagebox
import subprocess
from pathlib import Path

def launch_nexus():
    """Launch NEXUS with proper error handling"""
    nexus_dir = Path(__file__).parent
    
    # Try to launch NEXUS ULTIMATE first
    nexus_files = [
        "nexus_ULTIMATE.py",
        "nexus_COMPLETE.py", 
        "nexus.py"
    ]
    
    for nexus_file in nexus_files:
        nexus_path = nexus_dir / nexus_file
        if nexus_path.exists():
            try:
                print(f"🚀 Launching {nexus_file}...")
                os.chdir(nexus_dir)
                subprocess.run([sys.executable, str(nexus_path)], check=True)
                return
            except Exception as e:
                print(f"❌ Failed to launch {nexus_file}: {e}")
                continue
    
    # If all failed, show error
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "NEXUS Launch Error",
        "Could not start NEXUS application.\\n\\n"
        "Please check that all files are installed correctly."
    )

if __name__ == "__main__":
    launch_nexus()
'''
        
        launcher_path = package_dir / "launch_nexus.py"
        with open(launcher_path, 'w', encoding='utf-8') as f:
            f.write(launcher_content)
        
        print("  ✅ launch_nexus.py")
    
    def create_instructions(self, package_dir):
        """Create deployment instructions"""
        instructions = '''# NEXUS Desktop Installation Guide

## Quick Install (Windows)

1. **Extract** this ZIP file to any location
2. **Run** `Install_NEXUS_Desktop.bat` as Administrator
3. **Launch** NEXUS from desktop shortcut

## Manual Install

### Requirements
- Windows 10/11
- Python 3.9 or higher
- 2GB free disk space

### Steps
1. Install Python from https://python.org/downloads
2. Extract ZIP to desired location
3. Open Command Prompt in extracted folder
4. Run: `pip install -r requirements.txt`
5. Run: `python launch_nexus.py`

## Files Included

- `nexus_ULTIMATE.py` - Main application
- `launch_nexus.py` - Application launcher
- `requirements.txt` - Python dependencies
- `config/` - Configuration files
- `data/` - Database and cache
- `Install_NEXUS_Desktop.bat` - Windows installer

## Troubleshooting

### Python Not Found
Install Python from python.org and check "Add to PATH"

### Missing Modules
Run: `pip install -r requirements.txt`

### Permission Errors
Run installer as Administrator

### Database Issues  
Delete `data/` folder to reset database

## Support

For technical support, contact NEXUS development team.

---
NEXUS Collectibles Management System
Patent-Protected Technology
'''
        
        readme_path = package_dir / "README.txt"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(instructions)
        
        print("  ✅ README.txt")
    
    def create_zip(self, source_dir, zip_path):
        """Create ZIP package"""
        print("📦 Creating ZIP package...")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_dir.rglob('*'):
                if file_path.is_file():
                    arc_name = file_path.relative_to(source_dir)
                    zipf.write(file_path, arc_name)
        
        print(f"  ✅ {zip_path.name}")
    
    def get_size_mb(self, file_path):
        """Get file size in MB"""
        return file_path.stat().st_size / (1024 * 1024)

def main():
    """Main deployment function"""
    packager = NexusDesktopPackager()
    package_path = packager.create_package()
    
    print(f"\n📋 DEPLOYMENT READY:")
    print(f"   Send {package_path.name} to target PC")
    print(f"   Extract and run Install_NEXUS_Desktop.bat")
    print(f"   NEXUS will install automatically")

if __name__ == "__main__":
    main()