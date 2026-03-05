import serial
import time
import subprocess

# Arduino connection
ARDUINO_PORT = 'COM4'
BAUD_RATE = 9600

def trigger_nikon_camera():
    """Trigger Nikon camera using digiCamControl"""
    try:
        print("Triggering camera...")
        # Trigger camera using digiCamControl CLI
        result = subprocess.run(
            [r'C:\Program Files (x86)\digiCamControl\CameraControlCmd.exe', '/capture'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("Photo captured successfully")
            return True
        else:
            print(f"Camera error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("Camera timeout - took too long")
        return False
    except Exception as e:
        print(f"Camera error: {e}")
        return False

def main():
    print(f"Connecting to Arduino on {ARDUINO_PORT}...")
    
    try:
        ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)  # Wait for Arduino to reset
        print("Connected!")
        
        # Start automation
        ser.write(b'A\n')
        print("Automation started")
        
        while True:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                print(f"Arduino: {line}")
                
                # When card is ready for photo
                if "READY FOR PHOTO" in line:
                    time.sleep(0.5)  # Small delay for stability
                    
                    # Take photo
                    if trigger_nikon_camera():
                        # Photo successful, tell Arduino to continue
                        time.sleep(0.5)
                        ser.write(b'P\n')
                        print("Sent 'P' to Arduino - continuing cycle")
                    else:
                        print("Photo failed - waiting for retry...")
                        time.sleep(2)
                        ser.write(b'P\n')  # Continue anyway
    
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("\nStopping automation...")
        if 'ser' in locals() and ser.is_open:
            ser.write(b'A\n')  # Toggle auto mode off
            ser.close()
        print("Done")

if __name__ == "__main__":
    main()
