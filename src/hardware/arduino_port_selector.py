#!/usr/bin/env python3
"""
Arduino Port Selector - Standalone utility for selecting Arduino COM port
Allows manual port selection or auto-detection
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import time


class ArduinoPortSelector:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🔌 Arduino Port Selector")
        self.root.geometry("600x500")
        self.root.configure(bg="black")
        
        self.arduino = None
        self.selected_port = tk.StringVar(value="AUTO")
        
        self.create_gui()
        
    def create_gui(self):
        """Create the GUI interface"""
        # Title
        title = tk.Label(self.root, 
                        text="🔌 ARDUINO PORT SELECTOR",
                        font=("Arial", 20, "bold"),
                        fg="green", bg="black")
        title.pack(pady=20)
        
        # Port selection frame
        port_frame = ttk.LabelFrame(self.root, text="📡 COM Port Selection", padding=15)
        port_frame.pack(fill="x", padx=20, pady=10)
        
        # Port dropdown
        tk.Label(port_frame, text="Select Port:", 
                font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w", padx=5)
        
        self.port_selector = ttk.Combobox(port_frame, 
                                         textvariable=self.selected_port,
                                         values=["AUTO"],
                                         width=20,
                                         state="readonly")
        self.port_selector.grid(row=0, column=1, padx=10, pady=5)
        
        # Scan button
        tk.Button(port_frame, text="🔍 Scan for Ports",
                 command=self.scan_ports,
                 bg="blue", fg="white",
                 font=("Arial", 11, "bold")).grid(row=0, column=2, padx=5)
        
        # Connect button
        tk.Button(port_frame, text="🔌 Connect to Arduino",
                 command=self.connect_to_arduino,
                 bg="green", fg="white",
                 font=("Arial", 11, "bold")).grid(row=1, column=0, columnspan=3, pady=10)
        
        # Status frame
        status_frame = ttk.LabelFrame(self.root, text="📊 Connection Status", padding=15)
        status_frame.pack(fill="x", padx=20, pady=10)
        
        self.status_label = tk.Label(status_frame,
                                     text="🔴 Not Connected",
                                     font=("Arial", 14, "bold"),
                                     fg="red", bg="white")
        self.status_label.pack(pady=10)
        
        # Test frame
        test_frame = ttk.LabelFrame(self.root, text="🧪 Arduino Test Commands", padding=15)
        test_frame.pack(fill="x", padx=20, pady=10)
        
        test_buttons = tk.Frame(test_frame)
        test_buttons.pack()
        
        tk.Button(test_buttons, text="📊 Get Status",
                 command=lambda: self.send_command('S'),
                 bg="orange", fg="white",
                 font=("Arial", 10, "bold")).pack(side="left", padx=5)
        
        tk.Button(test_buttons, text="💡 LED Test",
                 command=lambda: self.send_command('L'),
                 bg="purple", fg="white",
                 font=("Arial", 10, "bold")).pack(side="left", padx=5)
        
        tk.Button(test_buttons, text="🔄 Reset",
                 command=lambda: self.send_command('E'),
                 bg="red", fg="white",
                 font=("Arial", 10, "bold")).pack(side="left", padx=5)
        
        # Output display
        output_frame = ttk.LabelFrame(self.root, text="📝 Output Log", padding=10)
        output_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.output_text = tk.Text(output_frame,
                                   height=10,
                                   bg="black", fg="green",
                                   font=("Courier", 10))
        self.output_text.pack(fill="both", expand=True)
        
        # Initialize log
        self.log("🚀 Arduino Port Selector Ready")
        self.log("=" * 60)
        self.log("Select a port or use AUTO to auto-detect")
        self.log("")
    
    def log(self, message):
        """Add message to output log"""
        self.output_text.insert("end", f"{message}\n")
        self.output_text.see("end")
    
    def scan_ports(self):
        """Scan for available COM ports"""
        self.log("\n🔍 SCANNING FOR COM PORTS...")
        self.log("=" * 60)
        
        ports = serial.tools.list_ports.comports()
        available_ports = ["AUTO"]
        
        if not ports:
            self.log("⚠️ No COM ports detected")
            messagebox.showwarning("No Ports Found", 
                                  "No COM ports were detected.\n\n"
                                  "Please check:\n"
                                  "• Arduino is plugged in via USB\n"
                                  "• Drivers are installed\n"
                                  "• USB cable is functional")
        else:
            for port in ports:
                available_ports.append(port.device)
                self.log(f"📡 Found: {port.device} - {port.description}")
            
            self.log(f"\n✅ Total ports found: {len(available_ports) - 1}")
        
        # Update dropdown
        self.port_selector['values'] = available_ports
        self.log("=" * 60 + "\n")
    
    def connect_to_arduino(self):
        """Connect to selected Arduino port"""
        selected = self.selected_port.get()
        
        # Close existing connection
        if self.arduino:
            try:
                self.arduino.close()
                self.log("🔌 Closed previous connection")
            except:
                pass
            self.arduino = None
        
        if selected == "AUTO":
            self.auto_detect_arduino()
        else:
            self.connect_to_port(selected)
    
    def auto_detect_arduino(self):
        """Auto-detect Arduino on all ports"""
        self.log("\n🔍 AUTO-DETECTING ARDUINO...")
        self.log("=" * 60)
        
        # Try common Arduino ports
        common_ports = ["COM1", "COM3", "COM4", "COM5", "COM6", 
                       "COM13", "COM14", "COM15"]
        
        # Add all detected ports
        all_ports = [p.device for p in serial.tools.list_ports.comports()]
        test_ports = list(set(common_ports + all_ports))
        
        for port in test_ports:
            if self.connect_to_port(port, auto_mode=True):
                return
        
        self.log("❌ Arduino not found on any port")
        self.status_label.config(text="🔴 Connection Failed", fg="red")
        messagebox.showerror("Connection Failed",
                           "Could not find Arduino on any port.\n\n"
                           "Please check:\n"
                           "• Arduino is powered on\n"
                           "• Firmware is uploaded\n"
                           "• USB connection is stable")
    
    def connect_to_port(self, port, auto_mode=False):
        """Connect to specific port"""
        if not auto_mode:
            self.log(f"\n🔌 Attempting connection to {port}...")
        
        try:
            # Open serial connection
            arduino = serial.Serial(port, 9600, timeout=2)
            time.sleep(2)  # Wait for Arduino reset
            
            # Test communication
            arduino.write(b'S')  # Status command
            time.sleep(0.5)
            
            response = arduino.readline().decode().strip()
            
            if response:
                self.arduino = arduino
                self.selected_port.set(port)
                self.log(f"✅ Successfully connected to {port}")
                self.log(f"📊 Arduino response: {response}")
                self.status_label.config(text=f"🟢 Connected ({port})", fg="green")
                
                messagebox.showinfo("Connection Successful",
                                   f"Arduino connected on {port}!\n\n"
                                   f"Response: {response}")
                return True
            else:
                if not auto_mode:
                    self.log(f"⚠️ No response from {port}")
                arduino.close()
                return False
                
        except serial.SerialException as e:
            if not auto_mode:
                self.log(f"❌ Error on {port}: {e}")
            return False
        except Exception as e:
            if not auto_mode:
                self.log(f"❌ Unexpected error on {port}: {e}")
            return False
    
    def send_command(self, command):
        """Send command to Arduino"""
        if not self.arduino:
            messagebox.showwarning("Not Connected",
                                  "Please connect to Arduino first!")
            return
        
        try:
            self.log(f"\n📤 Sending command: {command}")
            self.arduino.write(command.encode())
            time.sleep(0.5)
            
            # Read response
            response = self.arduino.readline().decode().strip()
            if response:
                self.log(f"📥 Response: {response}")
            else:
                self.log("⚠️ No response received")
                
        except Exception as e:
            self.log(f"❌ Error sending command: {e}")
            messagebox.showerror("Command Error", f"Failed to send command:\n{e}")
    
    def run(self):
        """Start the application"""
        self.root.mainloop()


if __name__ == "__main__":
    app = ArduinoPortSelector()
    app.run()
