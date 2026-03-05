"""
NEXUS Scanner Module
Integrates network scanner device with NEXUS GUI
"""

import tkinter as tk
from tkinter import messagebox
from scanner_interface import get_scanner
from datetime import datetime


class NexusScannerIntegration:
    """Manages scanner integration for NEXUS"""
    
    def __init__(self, parent_system):
        self.parent = parent_system
        self.scanner = get_scanner()
        self.last_scan_result = None
        self.batch_mode = False
        self.batch_results = []
        
    def check_scanner_status(self):
        """Check scanner device connection"""
        status = self.scanner.check_connection()
        return status
    
    def update_status_display(self, status_labels):
        """Update GUI status indicators"""
        status = self.check_scanner_status()
        
        if status['online']:
            status_labels['scanner'].config(
                text="🟢 Scanner Online (192.168.0.7)",
                fg="green"
            )
            
            if status['camera']:
                status_labels['camera'].config(
                    text="🟢 Camera Ready",
                    fg="green"
                )
            else:
                status_labels['camera'].config(
                    text="🟡 Camera Initializing",
                    fg="orange"
                )
            
            if status['arduino']:
                status_labels['arduino'].config(
                    text="🟢 Arduino Connected",
                    fg="green"
                )
            else:
                status_labels['arduino'].config(
                    text="🔴 Arduino Offline",
                    fg="red"
                )
        else:
            status_labels['scanner'].config(
                text=f"🔴 Scanner Offline - {status['message']}",
                fg="red"
            )
            status_labels['camera'].config(text="🔴 Not Available", fg="red")
            status_labels['arduino'].config(text="🔴 Not Available", fg="red")
        
        return status['online']
    
    def scan_single_card(self, result_callback=None):
        """Scan a single card"""
        result = self.scanner.scan_card()
        self.last_scan_result = result
        
        if result_callback:
            result_callback(result)
        
        return result
    
    def start_batch_scan(self):
        """Start batch scanning mode"""
        self.batch_mode = True
        self.batch_results = []
        messagebox.showinfo(
            "Batch Mode",
            "Batch scanning started. Scan cards one by one."
        )
    
    def stop_batch_scan(self):
        """Stop batch scanning and return results"""
        self.batch_mode = False
        results = self.batch_results.copy()
        self.batch_results = []
        return results
    
    def control_lights(self, on=True, brightness=200, color=(255, 255, 255)):
        """Control scanner lighting"""
        return self.scanner.set_lights(on, brightness, color)
    
    def run_hardware_test(self):
        """Run scanner hardware test"""
        return self.scanner.test_scanner()


def create_scanner_tab(nexus_system, notebook):
    """Create Card Scanner tab for NEXUS"""
    
    # Initialize scanner integration
    scanner_integration = NexusScannerIntegration(nexus_system)
    
    # Create tab
    scanner_frame = tk.Frame(notebook, bg='#0d0d0d')
    notebook.add(scanner_frame, text="📷 Card Scanner")
    
    # Header
    header = tk.Label(
        scanner_frame,
        text="📷 CARD SCANNER",
        font=("Perpetua", 24, "bold"),
        fg="#d4af37",
        bg='#0d0d0d'
    )
    header.pack(pady=20)
    
    # Status Section
    status_frame = tk.LabelFrame(
        scanner_frame,
        text="Scanner Status",
        font=("Perpetua", 14, "bold"),
        fg="#d4af37",
        bg='#1a1a1a',
        relief="ridge",
        borderwidth=2
    )
    status_frame.pack(fill="x", padx=20, pady=10)
    
    status_inner = tk.Frame(status_frame, bg='#1a1a1a')
    status_inner.pack(fill="x", padx=10, pady=10)
    
    status_labels = {}
    
    # Scanner status
    tk.Label(
        status_inner,
        text="Scanner Device:",
        font=("Arial", 12, "bold"),
        fg="#d4af37",
        bg='#1a1a1a'
    ).grid(row=0, column=0, sticky="w", pady=5)
    
    status_labels['scanner'] = tk.Label(
        status_inner,
        text="Checking...",
        font=("Arial", 12),
        fg="gray",
        bg='#1a1a1a'
    )
    status_labels['scanner'].grid(row=0, column=1, sticky="w", padx=20)
    
    # Camera status
    tk.Label(
        status_inner,
        text="Camera:",
        font=("Arial", 12, "bold"),
        fg="#d4af37",
        bg='#1a1a1a'
    ).grid(row=1, column=0, sticky="w", pady=5)
    
    status_labels['camera'] = tk.Label(
        status_inner,
        text="Checking...",
        font=("Arial", 12),
        fg="gray",
        bg='#1a1a1a'
    )
    status_labels['camera'].grid(row=1, column=1, sticky="w", padx=20)
    
    # Arduino status
    tk.Label(
        status_inner,
        text="Lighting (Arduino):",
        font=("Arial", 12, "bold"),
        fg="#d4af37",
        bg='#1a1a1a'
    ).grid(row=2, column=0, sticky="w", pady=5)
    
    status_labels['arduino'] = tk.Label(
        status_inner,
        text="Checking...",
        font=("Arial", 12),
        fg="gray",
        bg='#1a1a1a'
    )
    status_labels['arduino'].grid(row=2, column=1, sticky="w", padx=20)
    
    # Refresh button
    tk.Button(
        status_frame,
        text="🔄 Refresh Status",
        font=("Arial", 11),
        bg="#4b0082",
        fg="white",
        command=lambda: scanner_integration.update_status_display(status_labels)
    ).pack(pady=10)
    
    # Scan Controls Section
    controls_frame = tk.LabelFrame(
        scanner_frame,
        text="Scan Controls",
        font=("Perpetua", 14, "bold"),
        fg="#d4af37",
        bg='#1a1a1a',
        relief="ridge",
        borderwidth=2
    )
    controls_frame.pack(fill="x", padx=20, pady=10)
    
    buttons_inner = tk.Frame(controls_frame, bg='#1a1a1a')
    buttons_inner.pack(pady=15)
    
    def handle_scan():
        result_text.delete(1.0, tk.END)
        result_text.insert(1.0, "Scanning card...\n")
        scanner_frame.update()
        
        result = scanner_integration.scan_single_card()
        
        result_text.delete(1.0, tk.END)
        if result['success']:
            output = "=" * 60 + "\n"
            output += "✅ SCAN SUCCESSFUL\n"
            output += "=" * 60 + "\n\n"
            output += f"Card Name: {result['card_name']}\n"
            output += f"Set: {result['set_code']}\n"
            output += f"Confidence: {result['confidence']*100:.1f}%\n"
            output += f"Time: {result['timestamp']}\n"
            result_text.insert(1.0, output)
        else:
            output = "=" * 60 + "\n"
            output += "❌ SCAN FAILED\n"
            output += "=" * 60 + "\n\n"
            output += f"Error: {result.get('error', 'Unknown')}\n"
            result_text.insert(1.0, output)
    
    # Scan button
    tk.Button(
        buttons_inner,
        text="🎯 SCAN CARD",
        font=("Arial", 16, "bold"),
        bg="#27ae60",
        fg="white",
        width=20,
        height=2,
        command=handle_scan
    ).pack(pady=10)
    
    # Lighting controls
    lights_frame = tk.Frame(buttons_inner, bg='#1a1a1a')
    lights_frame.pack(pady=10)
    
    tk.Button(
        lights_frame,
        text="💡 Lights ON",
        font=("Arial", 11),
        bg="#3498db",
        fg="white",
        width=12,
        command=lambda: scanner_integration.control_lights(True)
    ).pack(side=tk.LEFT, padx=5)
    
    tk.Button(
        lights_frame,
        text="🌙 Lights OFF",
        font=("Arial", 11),
        bg="#95a5a6",
        fg="white",
        width=12,
        command=lambda: scanner_integration.control_lights(False)
    ).pack(side=tk.LEFT, padx=5)
    
    # Results Section
    results_frame = tk.LabelFrame(
        scanner_frame,
        text="Scan Results",
        font=("Perpetua", 14, "bold"),
        fg="#d4af37",
        bg='#1a1a1a',
        relief="ridge",
        borderwidth=2
    )
    results_frame.pack(fill="both", expand=True, padx=20, pady=10)
    
    result_text = tk.Text(
        results_frame,
        font=("Courier", 11),
        bg='#0d0d0d',
        fg='#d4af37',
        height=10,
        wrap=tk.WORD
    )
    result_text.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Initial status check
    scanner_integration.update_status_display(status_labels)
    
    return scanner_integration


def create_hardware_test_tab(nexus_system, notebook):
    """Create Hardware Test tab for NEXUS"""
    
    scanner = get_scanner()
    
    # Create tab
    test_frame = tk.Frame(notebook, bg='#0d0d0d')
    notebook.add(test_frame, text="🔧 Hardware Test")
    
    # Header
    header = tk.Label(
        test_frame,
        text="🔧 HARDWARE DIAGNOSTICS",
        font=("Perpetua", 24, "bold"),
        fg="#d4af37",
        bg='#0d0d0d'
    )
    header.pack(pady=20)
    
    # Test Controls
    controls_frame = tk.LabelFrame(
        test_frame,
        text="Hardware Tests",
        font=("Perpetua", 14, "bold"),
        fg="#d4af37",
        bg='#1a1a1a',
        relief="ridge",
        borderwidth=2
    )
    controls_frame.pack(fill="x", padx=20, pady=10)
    
    buttons_frame = tk.Frame(controls_frame, bg='#1a1a1a')
    buttons_frame.pack(pady=20)
    
    def run_connection_test():
        log_text.insert(tk.END, "\n" + "="*60 + "\n")
        log_text.insert(tk.END, "Testing Scanner Connection...\n")
        log_text.insert(tk.END, "="*60 + "\n")
        test_frame.update()
        
        status = scanner.check_connection()
        if status['online']:
            log_text.insert(tk.END, "✅ Scanner online at 192.168.0.7\n")
            log_text.insert(tk.END, f"   Camera: {'✅' if status['camera'] else '❌'}\n")
            log_text.insert(tk.END, f"   Arduino: {'✅' if status['arduino'] else '❌'}\n")
        else:
            log_text.insert(tk.END, f"❌ Scanner offline: {status['message']}\n")
        log_text.see(tk.END)
    
    def run_lighting_test():
        log_text.insert(tk.END, "\n" + "="*60 + "\n")
        log_text.insert(tk.END, "Testing Lighting System...\n")
        log_text.insert(tk.END, "="*60 + "\n")
        test_frame.update()
        
        if scanner.test_scanner():
            log_text.insert(tk.END, "✅ Rainbow test running on scanner\n")
        else:
            log_text.insert(tk.END, "❌ Lighting test failed\n")
        log_text.see(tk.END)
    
    def run_full_diagnostic():
        log_text.delete(1.0, tk.END)
        log_text.insert(1.0, "NEXUS SCANNER DIAGNOSTICS\n")
        log_text.insert(tk.END, f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_text.insert(tk.END, "="*60 + "\n\n")
        test_frame.update()
        
        run_connection_test()
        test_frame.after(1000)
        run_lighting_test()
    
    tk.Button(
        buttons_frame,
        text="🔌 Connection Test",
        font=("Arial", 13, "bold"),
        bg="#3498db",
        fg="white",
        width=18,
        command=run_connection_test
    ).grid(row=0, column=0, padx=10, pady=10)
    
    tk.Button(
        buttons_frame,
        text="💡 Lighting Test",
        font=("Arial", 13, "bold"),
        bg="#9b59b6",
        fg="white",
        width=18,
        command=run_lighting_test
    ).grid(row=0, column=1, padx=10, pady=10)
    
    tk.Button(
        buttons_frame,
        text="🔍 Full Diagnostic",
        font=("Arial", 13, "bold"),
        bg="#27ae60",
        fg="white",
        width=18,
        command=run_full_diagnostic
    ).grid(row=1, column=0, columnspan=2, pady=10)
    
    # Diagnostic Log
    log_frame = tk.LabelFrame(
        test_frame,
        text="Diagnostic Log",
        font=("Perpetua", 14, "bold"),
        fg="#d4af37",
        bg='#1a1a1a',
        relief="ridge",
        borderwidth=2
    )
    log_frame.pack(fill="both", expand=True, padx=20, pady=10)
    
    log_text = tk.Text(
        log_frame,
        font=("Courier", 10),
        bg='#0d0d0d',
        fg='#00ff00',
        height=15,
        wrap=tk.WORD
    )
    log_text.pack(fill="both", expand=True, padx=10, pady=10)
    
    log_text.insert(1.0, "Hardware diagnostics ready.\nClick a test button to begin.\n")
    
    return scanner
