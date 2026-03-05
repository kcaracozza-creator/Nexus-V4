"""
NEXUS Development Dashboard
Real-time monitoring and AI collaboration interface
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import json
import os
from pathlib import Path
from datetime import datetime
import threading
import time
import requests

class DevDashboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("NEX        uvicorn main:app --host 0.0.0.0 --port 8000US Dev Dashboard - AI Collaboration Monitor")
        self.root.geometry("1400x900")
        self.root.configure(bg="#0a0a0a")
        
        # Paths
        self.base_dir = Path(__file__).parent.absolute()
        self.messages_file = self.base_dir / "MENDEL_TO_CLOUSE.md"
        self.clouse_response = self.base_dir / "CLOUSE_TO_MENDEL.md"

        # NEXUS v2 Infrastructure
        self.zultan_url = "http://192.168.1.152:8000"  # GPU server, card API
        self.snarf_scanner_url = "http://192.168.1.219:5001"  # DANIELSON scanner
        self.snarf_acr_url = "http://192.168.1.219:5001"   # DANIELSON ACR
        self.brock_art_url = "http://192.168.1.219:5001"   # DANIELSON art server
        self.narwhal_url = "https://narwhal-council-relay.kcaracozza.workers.dev"
        self.marketplace_url = "https://nexus-marketplace-api.kcaracozza.workers.dev"
        
        self.setup_ui()
        self.start_monitoring()
        
    def setup_ui(self):
        # Title
        title = tk.Label(
            self.root, 
            text="🔧 NEXUS DEVELOPMENT DASHBOARD 🔧",
            font=("Consolas", 18, "bold"),
            bg="#0a0a0a",
            fg="#00ff00"
        )
        title.pack(pady=10)
        
        # Main container
        main_frame = tk.Frame(self.root, bg="#0a0a0a")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left column - System Status
        left_frame = tk.Frame(main_frame, bg="#1a1a1a", relief=tk.RIDGE, bd=2)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        tk.Label(
            left_frame,
            text="📊 SYSTEM STATUS",
            font=("Consolas", 12, "bold"),
            bg="#1a1a1a",
            fg="#00aaff"
        ).pack(pady=5)
        
        self.status_text = scrolledtext.ScrolledText(
            left_frame,
            width=50,
            height=20,
            bg="#000000",
            fg="#00ff00",
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Middle column - AI Chat Monitor
        middle_frame = tk.Frame(main_frame, bg="#1a1a1a", relief=tk.RIDGE, bd=2)
        middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        tk.Label(
            middle_frame,
            text="💬 AI COLLABORATION",
            font=("Consolas", 12, "bold"),
            bg="#1a1a1a",
            fg="#ff00ff"
        ).pack(pady=5)
        
        self.chat_text = scrolledtext.ScrolledText(
            middle_frame,
            width=50,
            height=20,
            bg="#000000",
            fg="#ffffff",
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Right column - Library Status
        right_frame = tk.Frame(main_frame, bg="#1a1a1a", relief=tk.RIDGE, bd=2)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        tk.Label(
            right_frame,
            text="📚 LIBRARY STATUS",
            font=("Consolas", 12, "bold"),
            bg="#1a1a1a",
            fg="#ffaa00"
        ).pack(pady=5)
        
        self.library_text = scrolledtext.ScrolledText(
            right_frame,
            width=50,
            height=20,
            bg="#000000",
            fg="#ffff00",
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        self.library_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Agent Message Windows - 4 columns showing each agent's messages
        agents_frame = tk.Frame(self.root, bg="#0a0a0a")
        agents_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tk.Label(
            agents_frame,
            text="🤖 AGENT MESSAGE STATUS",
            font=("Consolas", 12, "bold"),
            bg="#0a0a0a",
            fg="#ffaa00"
        ).pack(pady=5)

        agent_cols = tk.Frame(agents_frame, bg="#0a0a0a")
        agent_cols.pack(fill=tk.BOTH, expand=True)

        self.agent_windows = {}
        agents = [
            ("LOUIE", "#ff00ff", "Voice"),
            ("CLOUSE", "#00ffff", "Strategy"),
            ("MENDEL", "#00ff00", "Dev"),
            ("JAQUES", "#ffff00", "Legal")
        ]

        for agent_name, color, role in agents:
            frame = tk.Frame(agent_cols, bg="#1a1a1a", relief=tk.RIDGE, bd=2)
            frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)

            tk.Label(
                frame,
                text=f"{agent_name} ({role})",
                font=("Consolas", 10, "bold"),
                bg="#1a1a1a",
                fg=color
            ).pack(pady=3)

            text_widget = scrolledtext.ScrolledText(
                frame,
                width=25,
                height=10,
                bg="#000000",
                fg=color,
                font=("Consolas", 8),
                wrap=tk.WORD
            )
            text_widget.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
            self.agent_windows[agent_name] = text_widget

        # Bottom - Control Panel
        control_frame = tk.Frame(self.root, bg="#1a1a1a", relief=tk.RIDGE, bd=2)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(
            control_frame,
            text="⚡ QUICK ACTIONS",
            font=("Consolas", 10, "bold"),
            bg="#1a1a1a",
            fg="#ffffff"
        ).pack(pady=5)
        
        btn_frame = tk.Frame(control_frame, bg="#1a1a1a")
        btn_frame.pack(pady=5)
        
        tk.Button(
            btn_frame,
            text="🔄 Refresh Status",
            command=self.refresh_all,
            bg="#003300",
            fg="#00ff00",
            font=("Consolas", 10, "bold"),
            padx=10
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="📋 Copy Good Library",
            command=self.copy_library,
            bg="#330033",
            fg="#ff00ff",
            font=("Consolas", 10, "bold"),
            padx=10
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="🚀 Launch NEXUS",
            command=self.launch_nexus,
            bg="#003333",
            fg="#00ffff",
            font=("Consolas", 10, "bold"),
            padx=10
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="📝 View Mendel Message",
            command=self.view_mendel_message,
            bg="#333300",
            fg="#ffff00",
            font=("Consolas", 10, "bold"),
            padx=10
        ).pack(side=tk.LEFT, padx=5)

        # Narwhal Endpoints Toggle
        self.endpoints_button = tk.Button(
            btn_frame,
            text="🔒 Endpoints: ...",
            command=self.toggle_narwhal_endpoints,
            bg="#330000",
            fg="#ff6666",
            font=("Consolas", 10, "bold"),
            padx=10
        )
        self.endpoints_button.pack(side=tk.LEFT, padx=5)

        # Status bar
        self.status_bar = tk.Label(
            self.root,
            text="Monitoring started...",
            bg="#0a0a0a",
            fg="#00ff00",
            font=("Consolas", 9),
            anchor=tk.W
        )
        self.status_bar.pack(fill=tk.X, padx=10, pady=2)
        
    def log_status(self, message, color="#00ff00"):
        """Add message to status log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.update()
        
    def log_chat(self, message, sender="SYSTEM"):
        """Add message to chat log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.chat_text.insert(tk.END, f"[{timestamp}] {sender}:\n{message}\n\n")
        self.chat_text.see(tk.END)
        self.chat_text.update()
        
    def log_library(self, message):
        """Add message to library log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.library_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.library_text.see(tk.END)
        self.library_text.update()
        
    def check_library_status(self):
        """Check status of NEXUS library on ZULTAN"""
        self.library_text.delete(1.0, tk.END)
        self.log_library("=" * 50)
        self.log_library("NEXUS LIBRARY STATUS CHECK")
        self.log_library("=" * 50)

        # Check ZULTAN library via API
        try:
            response = requests.get(f"{self.zultan_url}/api/stats", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                self.log_library(f"\n🖥️  ZULTAN Library (192.168.1.152)")
                self.log_library(f"   Status: ✅ ONLINE")
                self.log_library(f"   MTG Cards: {stats.get('mtg', {}).get('total_cards', 0):,}")
                self.log_library(f"   Pokemon Cards: {stats.get('pokemon', {}).get('total_cards', 0):,}")
                self.log_library(f"   Sports Cards: {stats.get('sports', {}).get('total_cards', 0):,}")
            else:
                self.log_library(f"\n🖥️  ZULTAN Library")
                self.log_library(f"   Status: ⚠️  HTTP {response.status_code}")
        except requests.exceptions.Timeout:
            self.log_library(f"\n🖥️  ZULTAN Library")
            self.log_library(f"   Status: ⏱️  TIMEOUT")
        except requests.exceptions.ConnectionError:
            self.log_library(f"\n🖥️  ZULTAN Library")
            self.log_library(f"   Status: ❌ OFFLINE")
        except Exception as e:
            self.log_library(f"\n🖥️  ZULTAN Library")
            self.log_library(f"   Status: ❌ ERROR - {str(e)[:50]}")

        self.log_library("\n" + "=" * 50)
        
    def check_messages(self):
        """Check for AI messages"""
        # Check ZULTAN for any messages
        try:
            response = requests.get(f"{self.zultan_url}/api/health", timeout=2)
            if response.ok:
                self.log_chat("✅ ZULTAN API responding", "SYSTEM")
        except:
            self.log_chat("❌ ZULTAN offline", "SYSTEM")
        
        # Check Mendel's message
        if self.messages_file.exists():
            mod_time = datetime.fromtimestamp(self.messages_file.stat().st_mtime)
            self.log_chat(
                f"Mendel message found\nLast modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}\nSize: {self.messages_file.stat().st_size} bytes",
                "MENDEL"
            )
        
        # Check Clouse's response
        if self.clouse_response.exists():
            mod_time = datetime.fromtimestamp(self.clouse_response.stat().st_mtime)
            with open(self.clouse_response, 'r', encoding='utf-8') as f:
                content = f.read()
            self.log_chat(
                f"🚨 NEW MESSAGE FROM CLOUSE!\n\n{content[:500]}...",
                "CLOUSE"
            )
        else:
            self.log_chat("Waiting for Clouse's response...", "SYSTEM")
            
    def refresh_all(self):
        """Refresh all dashboard panels"""
        self.log_status("🔄 Refreshing all panels...")
        self.check_library_status()
        self.check_messages()
        self.check_system_files()
        self.log_status("✅ Refresh complete")
        self.status_bar.config(text=f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")
        
    def check_system_files(self):
        """Check NEXUS v2 infrastructure endpoints"""
        self.log_status("=" * 40)
        self.log_status("Checking NEXUS infrastructure...")

        # Check NEXUS v2 infrastructure endpoints
        endpoints_to_check = [
            (f"{self.zultan_url}/api/health", "ZULTAN (GPU Server)"),
            (f"{self.snarf_scanner_url}/health", "SNARF Scanner"),
            (f"{self.brock_art_url}/health", "BROCK Art Server"),
            (f"{self.narwhal_url}/sse", "Narwhal Council"),
            (f"{self.marketplace_url}/v1/cards", "Marketplace API"),
        ]

        for url, name in endpoints_to_check:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    self.log_status(f"✅ {name}: ONLINE")
                else:
                    self.log_status(f"⚠️  {name}: HTTP {response.status_code}")
            except requests.exceptions.Timeout:
                self.log_status(f"⏱️  {name}: TIMEOUT")
            except requests.exceptions.ConnectionError:
                self.log_status(f"❌ {name}: OFFLINE")
            except Exception as e:
                self.log_status(f"❌ {name}: ERROR - {str(e)[:30]}")

        self.log_status("=" * 40)
        
    def copy_library(self):
        """Check marketplace status"""
        self.log_status("📋 Checking marketplace API...")
        try:
            response = requests.get(f"{self.marketplace_url}/v1/cards", timeout=5)
            if response.status_code == 200:
                self.log_status("✅ Marketplace API: ONLINE")
            else:
                self.log_status(f"⚠️  Marketplace API: HTTP {response.status_code}")
        except Exception as e:
            self.log_status(f"❌ Marketplace API: {str(e)[:50]}")

    def launch_nexus(self):
        """Open NEXUS unified API in browser"""
        self.log_status("🚀 Opening ZULTAN API docs...")
        try:
            import webbrowser
            webbrowser.open(f"{self.zultan_url}/docs")
            self.log_status("✅ Opened API docs in browser")
        except Exception as e:
            self.log_status(f"❌ Failed to open browser: {e}")
            
    def view_mendel_message(self):
        """Open Mendel's message in new window"""
        if self.messages_file.exists():
            os.startfile(self.messages_file)
            self.log_status("📝 Opened Mendel's message")
        else:
            self.log_status("❌ No message file found")

    def update_agent_windows(self):
        """Update all 4 agent windows with live message data"""
        relay_url = "https://narwhal-council-relay.kcaracozza.workers.dev/mcp"

        for agent_name in ["LOUIE", "CLOUSE", "MENDEL", "JAQUES"]:
            try:
                # Get inbox messages
                resp_inbox = requests.post(relay_url, json={
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "get_messages", "arguments": {"agent": agent_name}}
                }, timeout=2)

                # Get outbox messages
                resp_outbox = requests.post(relay_url, json={
                    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "get_agent_outbox", "arguments": {"agent": agent_name, "limit": 5}}
                }, timeout=2)

                text_widget = self.agent_windows[agent_name]
                text_widget.delete(1.0, tk.END)

                if resp_inbox.ok:
                    inbox_data = resp_inbox.json()["result"]["content"][0]["text"]
                    inbox = json.loads(inbox_data)

                    outbox_data = resp_outbox.json()["result"]["content"][0]["text"]
                    outbox = json.loads(outbox_data)

                    # Show status
                    text_widget.insert(tk.END, f"INBOX: {inbox['total_messages']} msgs\n")
                    text_widget.insert(tk.END, f"Unread: {inbox['unread_count']}\n")
                    text_widget.insert(tk.END, f"OUTBOX: {outbox['total_sent']} sent\n\n")

                    # Show recent inbox
                    text_widget.insert(tk.END, "Recent IN:\n")
                    for msg in inbox['messages'][-3:]:
                        status_icon = "✓" if msg.get('status') == 'read' else "●"
                        text_widget.insert(tk.END, f"{status_icon} {msg['from']}: {msg['message'][:30]}...\n")

                    # Show recent outbox
                    text_widget.insert(tk.END, "\nRecent OUT:\n")
                    for msg in outbox['messages'][-3:]:
                        text_widget.insert(tk.END, f"→ {msg['to']}: {msg['message'][:30]}...\n")

                    text_widget.insert(tk.END, f"\n[ONLINE]")
                else:
                    text_widget.insert(tk.END, f"[ERROR]\nCannot reach Narwhal")

            except Exception as e:
                text_widget = self.agent_windows[agent_name]
                text_widget.delete(1.0, tk.END)
                text_widget.insert(tk.END, f"[OFFLINE]\n{str(e)[:50]}")

    def check_narwhal_status(self):
        """Check if Narwhal endpoints are enabled"""
        try:
            response = requests.get(
                "https://narwhal-council-relay.kcaracozza.workers.dev/admin/endpoints-status",
                timeout=3
            )
            if response.ok:
                data = response.json()
                enabled = data.get('endpoints_enabled', True)
                status_text = "OPEN" if enabled else "CLOSED"
                color = "#00ff00" if enabled else "#ff0000"
                icon = "🔓" if enabled else "🔒"

                self.endpoints_button.config(
                    text=f"{icon} Endpoints: {status_text}",
                    bg="#003300" if enabled else "#330000",
                    fg=color
                )
                return enabled
            return None
        except Exception as e:
            self.log_status(f"⚠️ Narwhal check failed: {e}")
            return None

    def toggle_narwhal_endpoints(self):
        """Toggle Narwhal /call/* endpoints on/off"""
        try:
            # Get current status
            current_status = self.check_narwhal_status()
            if current_status is None:
                self.log_status("❌ Cannot reach Narwhal relay")
                return

            # Toggle to opposite
            new_status = not current_status

            response = requests.post(
                "https://narwhal-council-relay.kcaracozza.workers.dev/admin/toggle-endpoints",
                json={"enabled": new_status},
                timeout=3
            )

            if response.ok:
                data = response.json()
                status_text = "ENABLED" if new_status else "DISABLED"
                self.log_status(f"✅ Narwhal endpoints {status_text}")
                self.log_chat(f"Endpoints {status_text} - /call/louie, /call/mendel, /call/jaques", "NARWHAL")

                # Update button
                self.check_narwhal_status()
            else:
                self.log_status(f"❌ Toggle failed: {response.text}")

        except Exception as e:
            self.log_status(f"❌ Toggle error: {e}")

    def monitor_loop(self):
        """Background monitoring thread"""
        last_clouse_check = 0
        update_counter = 0

        while True:
            try:
                # Check for new Clouse response every 5 seconds
                if self.clouse_response.exists():
                    mod_time = self.clouse_response.stat().st_mtime
                    if mod_time > last_clouse_check:
                        last_clouse_check = mod_time
                        self.root.after(0, self.check_messages)
                        self.root.after(0, lambda: self.log_status("🔔 New message from Clouse detected!"))

                # Update agent windows every 10 seconds (every 2nd loop)
                update_counter += 1
                if update_counter >= 2:
                    update_counter = 0
                    self.root.after(0, self.update_agent_windows)
                    self.root.after(0, self.check_narwhal_status)

                time.sleep(5)
            except Exception as e:
                print(f"Monitor error: {e}")
                
    def start_monitoring(self):
        """Start background monitoring"""
        self.log_status("🎯 Dashboard initialized")
        self.log_status("👁️ Monitoring AI communication...")
        self.check_narwhal_status()
        self.update_agent_windows()
        self.refresh_all()
        
        # Start background thread
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        
    def run(self):
        """Start the dashboard"""
        self.root.mainloop()

if __name__ == "__main__":
    dashboard = DevDashboard()
    dashboard.run()
