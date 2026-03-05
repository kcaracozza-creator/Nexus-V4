import serial
import time

print("Quick Arduino Control")
print("=" * 50)

try:
    arduino = serial.Serial('COM13', 115200, timeout=1)
    time.sleep(2)  # Wait for reset
    
    # Clear buffer
    while arduino.in_waiting:
        arduino.readline()
    
    while True:
        print("\nCommands: ON, OFF, B<0-255>, C<R,G,B>, TEST, STATUS, QUIT")
        cmd = input("Enter command: ").strip().upper()
        
        if cmd == "QUIT":
            break
        
        if cmd:
            arduino.write((cmd + "\n").encode())
            arduino.flush()
            time.sleep(0.1)
            
            # Read all responses
            while arduino.in_waiting:
                response = arduino.readline().decode('utf-8', errors='ignore').strip()
                if response:
                    print(f"  → {response}")
    
    arduino.close()
    print("\nArduino control closed")
    
except KeyboardInterrupt:
    print("\n\nExiting...")
except Exception as e:
    print(f"\nError: {e}")
