#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arduino Uploader - SD Card Sketch Upload
Premium feature: Auto-upload Arduino sketches from SD card
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import serial.tools.list_ports
import time

class ArduinoUploader:
    """
    Upload Arduino sketches from SD card to connected boards
    Supports .ino source files and .hex pre-compiled binaries
    """
    
    # Board configurations
    BOARDS = {
        'uno': {
            'fqbn': 'arduino:avr:uno',
            'programmer': 'arduino',
            'mcu': 'atmega328p',
            'baudrate': 115200
        },
        'nano': {
            'fqbn': 'arduino:avr:nano:cpu=atmega328',
            'programmer': 'arduino',
            'mcu': 'atmega328p',
            'baudrate': 57600
        },
        'mega': {
            'fqbn': 'arduino:avr:mega:cpu=atmega2560',
            'programmer': 'wiring',
            'mcu': 'atmega2560',
            'baudrate': 115200
        },
        'leonardo': {
            'fqbn': 'arduino:avr:leonardo',
            'programmer': 'avr109',
            'mcu': 'atmega32u4',
            'baudrate': 57600
        },
        'esp32': {
            'fqbn': 'esp32:esp32:esp32',
            'programmer': 'esptool',
            'mcu': 'esp32',
            'baudrate': 921600
        }
    }
    
    def __init__(self):
        """Initialize uploader"""
        self.detected_boards = []
        self.upload_log = []
    
    def detect_arduino_boards(self):
        """Auto-detect connected Arduino boards"""
        print("🔍 Detecting Arduino boards...")
        
        ports = serial.tools.list_ports.comports()
        self.detected_boards = []
        
        for port in ports:
            # Check for Arduino VID/PID
            if port.vid and port.pid:
                board_type = self._identify_board(port.vid, port.pid)
                if board_type:
                    self.detected_boards.append({
                        'port': port.device,
                        'type': board_type,
                        'description': port.description
                    })
                    print(f"   ✓ {board_type.upper()} on {port.device}")
        
        if not self.detected_boards:
            print("   ⚠️ No Arduino boards detected")
            print("   💡 Check USB connection and drivers")
        
        return self.detected_boards
    
    def _identify_board(self, vid, pid):
        """Identify board type from USB VID/PID"""
        # Arduino VID: 0x2341, CH340: 0x1A86, FTDI: 0x0403
        if vid == 0x2341:  # Official Arduino
            if pid in [0x0043, 0x0001]:
                return 'uno'
            elif pid in [0x8036, 0x0036]:
                return 'leonardo'
            elif pid == 0x0042:
                return 'mega'
        elif vid == 0x1A86:  # CH340 (cheap clones)
            return 'nano'  # Assume Nano with CH340
        elif vid == 0x0403:  # FTDI
            return 'nano'  # Assume Nano with FTDI
        elif vid == 0x10C4:  # Silicon Labs (ESP32)
            return 'esp32'
        
        return None
    
    def scan_sd_card(self, sd_path='/media/sdcard'):
        """Scan SD card for Arduino sketches"""
        sd_path = Path(sd_path)
        
        sketches = {
            'ino': list(sd_path.glob('**/*.ino')),
            'hex': list(sd_path.glob('**/*.hex')),
            'bin': list(sd_path.glob('**/*.bin'))
        }
        
        total = sum(len(files) for files in sketches.values())
        
        print(f"\n📁 Found on SD card:")
        print(f"   .ino sketches: {len(sketches['ino'])}")
        print(f"   .hex binaries: {len(sketches['hex'])}")
        print(f"   .bin firmware: {len(sketches['bin'])}")
        
        return sketches
    
    def compile_sketch(self, sketch_path, board_type='uno'):
        """Compile Arduino sketch using arduino-cli"""
        print(f"\n🔨 Compiling {sketch_path.name}...")
        
        board_config = self.BOARDS[board_type]
        
        # Check if arduino-cli is available
        if not self._check_arduino_cli():
            print("   ⚠️ arduino-cli not found, trying avrdude for .hex files")
            return None
        
        # Compile command
        cmd = [
            'arduino-cli', 'compile',
            '--fqbn', board_config['fqbn'],
            str(sketch_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Find compiled hex file
                hex_file = sketch_path.parent / f"{sketch_path.stem}.ino.hex"
                if hex_file.exists():
                    print(f"   ✅ Compiled successfully")
                    return hex_file
                else:
                    print(f"   ❌ Compilation succeeded but .hex not found")
                    return None
            else:
                print(f"   ❌ Compilation failed:")
                print(result.stderr)
                return None
                
        except subprocess.TimeoutExpired:
            print(f"   ❌ Compilation timed out")
            return None
        except Exception as e:
            print(f"   ❌ Compilation error: {e}")
            return None
    
    def upload_hex(self, hex_path, port, board_type='uno'):
        """Upload compiled .hex file using avrdude"""
        print(f"\n📤 Uploading {hex_path.name} to {port}...")
        
        board_config = self.BOARDS[board_type]
        
        # avrdude command
        cmd = [
            'avrdude',
            '-c', board_config['programmer'],
            '-p', board_config['mcu'],
            '-P', port,
            '-b', str(board_config['baudrate']),
            '-D',  # Disable auto erase for flash
            '-U', f"flash:w:{hex_path}:i"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print(f"   ✅ Upload successful!")
                self.upload_log.append({
                    'file': hex_path.name,
                    'port': port,
                    'board': board_type,
                    'status': 'success',
                    'time': time.time()
                })
                return True
            else:
                print(f"   ❌ Upload failed:")
                print(result.stderr)
                self.upload_log.append({
                    'file': hex_path.name,
                    'port': port,
                    'board': board_type,
                    'status': 'failed',
                    'error': result.stderr,
                    'time': time.time()
                })
                return False
                
        except subprocess.TimeoutExpired:
            print(f"   ❌ Upload timed out")
            return False
        except Exception as e:
            print(f"   ❌ Upload error: {e}")
            return False
    
    def upload_sketch(self, sketch_path, port=None, board_type='uno'):
        """Complete upload workflow: compile + upload"""
        print(f"\n{'='*60}")
        print(f"🚀 UPLOADING ARDUINO SKETCH")
        print(f"{'='*60}")
        print(f"Sketch: {sketch_path}")
        print(f"Board: {board_type.upper()}")
        print(f"Port: {port or 'auto-detect'}")
        print(f"{'='*60}")
        
        # Auto-detect board if port not specified
        if not port:
            self.detect_arduino_boards()
            if self.detected_boards:
                port = self.detected_boards[0]['port']
                board_type = self.detected_boards[0]['type']
                print(f"\n✓ Using auto-detected {board_type.upper()} on {port}")
            else:
                print("\n❌ No Arduino boards found")
                return False
        
        # Check file type
        sketch_path = Path(sketch_path)
        
        if sketch_path.suffix == '.hex':
            # Direct upload of pre-compiled hex
            return self.upload_hex(sketch_path, port, board_type)
        
        elif sketch_path.suffix == '.ino':
            # Compile then upload
            hex_file = self.compile_sketch(sketch_path, board_type)
            if hex_file:
                return self.upload_hex(hex_file, port, board_type)
            else:
                return False
        
        else:
            print(f"❌ Unsupported file type: {sketch_path.suffix}")
            return False
    
    def _check_arduino_cli(self):
        """Check if arduino-cli is installed"""
        try:
            subprocess.run(['arduino-cli', 'version'], 
                         capture_output=True, check=True)
            return True
        except:
            return False
    
    def write_upload_log(self, sd_path='/media/sdcard'):
        """Write upload log to SD card"""
        log_file = Path(sd_path) / 'ARDUINO_UPLOAD_LOG.txt'
        
        with open(log_file, 'w') as f:
            f.write("ARDUINO UPLOAD LOG\n")
            f.write("=" * 60 + "\n\n")
            
            for entry in self.upload_log:
                f.write(f"File: {entry['file']}\n")
                f.write(f"Board: {entry['board']}\n")
                f.write(f"Port: {entry['port']}\n")
                f.write(f"Status: {entry['status'].upper()}\n")
                if 'error' in entry:
                    f.write(f"Error: {entry['error']}\n")
                f.write(f"Time: {time.ctime(entry['time'])}\n")
                f.write("-" * 60 + "\n")
        
        print(f"\n📝 Upload log written to {log_file}")


def main():
    parser = argparse.ArgumentParser(description='Arduino SD Card Uploader')
    parser.add_argument('--sketch', help='Path to .ino or .hex file')
    parser.add_argument('--board', default='uno', 
                       choices=['uno', 'nano', 'mega', 'leonardo', 'esp32'],
                       help='Board type')
    parser.add_argument('--port', help='Serial port (auto-detect if not specified)')
    parser.add_argument('--sd-path', default='/media/sdcard', 
                       help='SD card mount point')
    parser.add_argument('--scan-only', action='store_true',
                       help='Only scan SD card, don\'t upload')
    
    args = parser.parse_args()
    
    uploader = ArduinoUploader()
    
    # Detect boards
    uploader.detect_arduino_boards()
    
    # Scan SD card
    sketches = uploader.scan_sd_card(args.sd_path)
    
    if args.scan_only:
        return
    
    # Upload specified sketch
    if args.sketch:
        success = uploader.upload_sketch(args.sketch, args.port, args.board)
        uploader.write_upload_log(args.sd_path)
        sys.exit(0 if success else 1)
    
    # Auto-upload all .ino files found on SD card
    elif sketches['ino']:
        print("\n🚀 Auto-uploading all sketches from SD card...")
        for sketch in sketches['ino']:
            uploader.upload_sketch(sketch, args.port, args.board)
            time.sleep(2)  # Pause between uploads
        
        uploader.write_upload_log(args.sd_path)
    
    else:
        print("\n💡 No sketches to upload")
        print("   Use --sketch to specify a file, or add .ino files to SD card")


if __name__ == "__main__":
    main()
