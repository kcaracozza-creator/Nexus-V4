#!/usr/bin/env python3
"""
NEXUS ESP32 Serial Diagnostic
===============================
Run this on the scanner laptop to figure out why the ESP32 won't talk.
Tests: port detection, driver status, communication, and firmware response.

Usage: python esp32_diagnostic.py
"""
import sys
import time

# Step 1: Check if pyserial is installed
try:
    import serial
    import serial.tools.list_ports
    print("✅ pyserial installed")
except ImportError:
    print("❌ pyserial NOT installed")
    print("   Fix: pip install pyserial")
    print("   Then run this again.")
    sys.exit(1)

print("\n" + "="*60)
print("NEXUS ESP32 SERIAL DIAGNOSTIC")
print("="*60)

# Step 2: List ALL serial ports
print("\n📡 SCANNING FOR SERIAL PORTS...\n")
ports = list(serial.tools.list_ports.comports())

if not ports:
    print("❌ NO SERIAL PORTS FOUND AT ALL")
    print("")
    print("This means one of:")
    print("  1. ESP32 is not plugged into USB")
    print("  2. USB cable is charge-only (no data)")
    print("  3. Driver not installed")
    print("")
    print("FIXES:")
    print("  → Try a different USB cable (must be DATA cable)")
    print("  → Check Device Manager for unknown devices")
    print("  → Install CP2102 driver: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers")
    print("  → Install CH340 driver: http://www.wch-ic.com/downloads/CH341SER_EXE.html")
    print("")
    print("After plugging in ESP32, check Device Manager:")
    print("  Win+X → Device Manager → Ports (COM & LPT)")
    print("  Look for 'Silicon Labs CP210x' or 'CH340'")
    sys.exit(1)

print(f"Found {len(ports)} serial port(s):\n")
esp32_port = None

for p in ports:
    is_esp = False
    chip = "Unknown"
    
    # Detect common ESP32 USB-serial chips
    desc = (p.description or "").lower()
    hwid = (p.hwid or "").lower()
    
    if "cp210" in desc or "cp210" in hwid or "10c4:ea60" in hwid:
        chip = "CP2102 (Silicon Labs)"
        is_esp = True
    elif "ch340" in desc or "ch340" in hwid or "1a86:7523" in hwid:
        chip = "CH340"
        is_esp = True
    elif "ch9102" in desc or "ch9102" in hwid:
        chip = "CH9102"
        is_esp = True
    elif "ftdi" in desc or "0403:6001" in hwid:
        chip = "FTDI"
        is_esp = True
    
    status = "⚡ LIKELY ESP32" if is_esp else "  (probably not ESP32)"
    
    print(f"  {status}")
    print(f"  Port:        {p.device}")
    print(f"  Description: {p.description}")
    print(f"  Chip:        {chip}")
    print(f"  Hardware ID: {p.hwid}")
    print()
    
    if is_esp and esp32_port is None:
        esp32_port = p.device

if esp32_port is None:
    print("⚠️  No ESP32-like port detected.")
    print("   Trying first available port anyway...")
    esp32_port = ports[0].device

# Step 3: Try to communicate
print("="*60)
print(f"🔌 TESTING COMMUNICATION ON {esp32_port}")
print("="*60)
print()

BAUD = 115200

try:
    ser = serial.Serial(
        port=esp32_port,
        baudrate=BAUD,
        timeout=3,
        write_timeout=3
    )
    print(f"✅ Port {esp32_port} opened at {BAUD} baud")
except serial.SerialException as e:
    print(f"❌ FAILED to open {esp32_port}: {e}")
    print("")
    print("Common causes:")
    print("  → Port in use by Arduino IDE (close it)")
    print("  → Port in use by another program")
    print("  → Wrong port — check Device Manager")
    print("  → Permission issue")
    sys.exit(1)

# Give ESP32 time to reset after serial connection
print("   Waiting 2s for ESP32 to boot after reset...")
time.sleep(2)

# Flush any boot messages
boot_data = ser.read(ser.in_waiting or 1)
if boot_data:
    print(f"   Boot output: {boot_data.decode('utf-8', errors='replace').strip()}")

# Step 4: Send STATUS command
print(f"\n📤 Sending: STATUS")
ser.write(b'STATUS\n')
time.sleep(1)

response = ser.read(ser.in_waiting or 256)
if response:
    text = response.decode('utf-8', errors='replace').strip()
    print(f"📥 Response: {text}")
    print(f"\n✅✅✅ ESP32 IS TALKING! Communication works!")
else:
    print(f"📥 Response: (nothing)")
    print(f"\n⚠️  No response to STATUS command.")
    print()
    
    # Try L1 (lights on)
    print("📤 Trying: L1 (lights on)")
    ser.write(b'L1\n')
    time.sleep(1)
    
    response = ser.read(ser.in_waiting or 256)
    if response:
        text = response.decode('utf-8', errors='replace').strip()
        print(f"📥 Response: {text}")
        print(f"\n✅ ESP32 responded to L1!")
        
        # Turn lights back off
        ser.write(b'L0\n')
        time.sleep(0.5)
        ser.read(ser.in_waiting or 256)
    else:
        print(f"📥 Response: (nothing)")
        print()
        print("❌ ESP32 NOT RESPONDING")
        print()
        print("Possible issues:")
        print("  1. WRONG BAUD RATE — firmware might not be 115200")
        print("  2. ESP32 NOT FLASHED — needs firmware uploaded via Arduino IDE")
        print("  3. ESP32 IN BOOT MODE — hold BOOT button, press RST, release BOOT")
        print("  4. TX/RX WIRING — if using external UART, check TX→RX crossover")
        print("  5. WRONG PORT — might be talking to something else")
        print()
        print("QUICK TEST: Open Arduino IDE → Serial Monitor → 115200 baud")
        print("Type 'STATUS' and press Enter. See if anything comes back.")

# Step 5: Test all basic commands
if response:
    print("\n" + "="*60)
    print("🧪 RUNNING FULL COMMAND TEST")
    print("="*60)
    
    commands = [
        ("L1", "Lights ON"),
        ("B200", "Brightness 200"),
        ("STATUS", "Status check"),
        ("L0", "Lights OFF"),
    ]
    
    for cmd, desc in commands:
        ser.write(f'{cmd}\n'.encode())
        time.sleep(0.5)
        resp = ser.read(ser.in_waiting or 256)
        resp_text = resp.decode('utf-8', errors='replace').strip() if resp else "(no response)"
        status = "✅" if resp else "⚠️"
        print(f"  {status} {cmd:10s} ({desc:20s}) → {resp_text}")
    
    print()
    print("🎉 DIAGNOSTIC COMPLETE — ESP32 is communicating!")
    print(f"   Port: {esp32_port}")
    print(f"   Baud: {BAUD}")
    print()
    print("Use this in your scanner code:")
    print(f'   import serial')
    print(f'   esp = serial.Serial("{esp32_port}", {BAUD})')
    print(f'   esp.write(b"L1\\n")  # Lights on')
    print(f'   esp.write(b"SCAN\\n")  # Full scan sequence')

ser.close()
print("\n✅ Port closed. Done.")
