@echo off
echo ========================================
echo Checking for Arduino COM Ports...
echo ========================================
echo.

powershell -Command "Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description, Status | Format-Table -AutoSize"

echo.
echo ========================================
echo Arduino Detection
echo ========================================
echo.

wmic path Win32_SerialPort get DeviceID,Description,Status 2>nul | findstr /i "arduino usb com"

if %errorlevel% neq 0 (
    echo [WARNING] No Arduino found!
    echo.
    echo Possible issues:
    echo 1. Arduino not connected via USB
    echo 2. Arduino drivers not installed
    echo 3. USB cable is power-only (no data)
    echo.
    echo Try:
    echo - Unplug and replug Arduino USB
    echo - Try different USB port
    echo - Check Device Manager for "Unknown Device"
) else (
    echo.
    echo [SUCCESS] Arduino detected!
    echo Use the COM port shown above in Arduino IDE
)

echo.
echo ========================================
pause
