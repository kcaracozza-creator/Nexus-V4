"""
AI Bridge - Automatic Communication System
Monitors Downloads folder and auto-syncs messages between Clouse and Mendel
"""

import time
import shutil
from pathlib import Path
from datetime import datetime
import json

class AIBridge:
    def __init__(self):
        self.downloads = Path("E:/Downloads")
        self.workspace = Path("E:/MTTGG/PYTHON SOURCE FILES")
        
        # Message files
        self.clouse_message = "CLOUSE_TO_MENDEL.md"
        self.mendel_message = "MENDEL_TO_CLOUSE.md"
        
        # Tracking
        self.last_clouse_check = 0
        self.message_log = self.workspace / "ai_chat_log.json"
        
        # Initialize log
        if not self.message_log.exists():
            self.save_log([])
    
    def save_log(self, messages):
        """Save message history"""
        with open(self.message_log, 'w', encoding='utf-8') as f:
            json.dump(messages, f, indent=2)
    
    def load_log(self):
        """Load message history"""
        try:
            with open(self.message_log, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def check_for_clouse_message(self):
        """Check if Clouse dropped a new message in Downloads"""
        clouse_in_downloads = self.downloads / self.clouse_message
        clouse_in_workspace = self.workspace / self.clouse_message
        
        if clouse_in_downloads.exists():
            mod_time = clouse_in_downloads.stat().st_mtime
            
            # New message?
            if mod_time > self.last_clouse_check:
                print(f"\n🔔 NEW MESSAGE FROM CLOUSE DETECTED!")
                print(f"   Time: {datetime.fromtimestamp(mod_time).strftime('%H:%M:%S')}")
                
                # Copy to workspace
                shutil.copy2(clouse_in_downloads, clouse_in_workspace)
                print(f"   ✅ Copied to workspace")
                
                # Log it
                with open(clouse_in_workspace, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                messages = self.load_log()
                messages.append({
                    'from': 'CLOUSE',
                    'to': 'MENDEL',
                    'timestamp': datetime.now().isoformat(),
                    'content': content[:200] + "..." if len(content) > 200 else content
                })
                self.save_log(messages)
                
                self.last_clouse_check = mod_time
                return True
        
        return False
    
    def sync_mendel_message(self):
        """Copy Mendel's message to Downloads for Kevin to send to Clouse"""
        mendel_in_workspace = self.workspace / self.mendel_message
        mendel_in_downloads = self.downloads / self.mendel_message
        
        if mendel_in_workspace.exists():
            # Check if Downloads version is older
            if not mendel_in_downloads.exists() or \
               mendel_in_workspace.stat().st_mtime > mendel_in_downloads.stat().st_mtime:
                
                shutil.copy2(mendel_in_workspace, mendel_in_downloads)
                print(f"📤 Mendel's message synced to Downloads")
                print(f"   Kevin can now send to Clouse")
                return True
        
        return False
    
    def watch_downloads(self):
        """Monitor Downloads folder for new Clouse messages"""
        print("=" * 60)
        print("🤖 AI BRIDGE ACTIVE")
        print("=" * 60)
        print(f"Monitoring: {self.downloads}")
        print(f"Workspace:  {self.workspace}")
        print(f"\nWatching for: {self.clouse_message}")
        print(f"Auto-syncing: {self.mendel_message}")
        print("\nPress Ctrl+C to stop\n")
        
        try:
            while True:
                # Check for Clouse's messages
                if self.check_for_clouse_message():
                    print("\n💬 CLOUSE SAYS SOMETHING!")
                    print("   Check dev_dashboard.py or read CLOUSE_TO_MENDEL.md\n")
                
                # Sync Mendel's messages
                self.sync_mendel_message()
                
                # Wait 3 seconds
                time.sleep(3)
                
        except KeyboardInterrupt:
            print("\n\n🛑 AI Bridge stopped")
            print(f"Message log: {self.message_log}")
    
    def show_history(self):
        """Display message history"""
        messages = self.load_log()
        
        print("\n" + "=" * 60)
        print("📜 AI CHAT HISTORY")
        print("=" * 60)
        
        if not messages:
            print("\nNo messages yet.")
        else:
            for i, msg in enumerate(messages, 1):
                print(f"\n[{i}] {msg['from']} → {msg['to']}")
                print(f"    {msg['timestamp']}")
                print(f"    {msg['content'][:150]}...")
        
        print("\n" + "=" * 60)

if __name__ == "__main__":
    import sys
    
    bridge = AIBridge()
    
    if len(sys.argv) > 1 and sys.argv[1] == "history":
        bridge.show_history()
    else:
        bridge.watch_downloads()
