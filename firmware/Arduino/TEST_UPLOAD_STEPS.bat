@echo off
echo ========================================
echo MTTGG Arduino Upload Test Helper
echo ========================================
echo.
echo STEP 1: Upload Ultra Simple Test
echo ---------------------------------
echo 1. Open Arduino IDE
echo 2. File ^> Open: E:\MTTGG\Arduino\arduino_test_ultra_simple.ino
echo 3. Tools ^> Board ^> Arduino Uno
echo 4. Tools ^> Port ^> COM5 (or your Arduino port)
echo 5. Click Upload (arrow button)
echo.
echo EXPECTED RESULT:
echo - Pin 13 LED blinks every second
echo - Serial Monitor shows "LED ON" / "LED OFF"
echo.
echo ========================================
echo.
echo STEP 2: If Step 1 works, try Basic Test
echo ---------------------------------
echo 1. File ^> Open: E:\MTTGG\Arduino\arduino_test_basic.ino
echo 2. Upload (same process)
echo.
echo EXPECTED RESULT:
echo - Pin 13 LED blinks
echo - NeoPixels on Pin 9 turn GREEN
echo - Serial Monitor shows "HEARTBEAT"
echo.
echo ========================================
echo.
echo STEP 3: If Step 2 works, upload Full v4.0
echo ---------------------------------
echo 1. File ^> Open: E:\MTTGG\Arduino\arduino_scanner_firmware_v4_0_full_automation.ino
echo 2. Upload
echo.
echo EXPECTED RESULT:
echo - Pin 13 LED stays ON (ready state)
echo - NeoPixels turn GREEN
echo - Serial Monitor shows "MTTGG Scanner v4.0 Ready"
echo.
echo ========================================
echo.
echo TROUBLESHOOTING:
echo ---------------------------------
echo If NOTHING happens on Arduino:
echo.
echo 1. CHECK USB CABLE - try different cable/port
echo 2. CHECK BOARD SELECTION - must be "Arduino Uno"
echo 3. CHECK PORT - Device Manager ^> Ports ^> COM5?
echo 4. LOOK FOR ERRORS in Arduino IDE output window
echo.
echo If upload says "Done uploading" but LED doesn't work:
echo - Arduino may be damaged
echo - Try pressing RESET button on Arduino
echo - Check if Pin 13 LED exists on your board
echo.
echo ========================================
pause
