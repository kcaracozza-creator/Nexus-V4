#!/usr/bin/env python3
"""
NEXUS Messenger Bot - CLOUSE
Monitors web messenger and auto-responds as Clouse
"""
import requests
import time
from datetime import datetime

SERVER_URL = "http://192.168.1.152:8000"
POLL_INTERVAL = 3  # seconds
MY_NAME = "clouse"

class MessengerBot:
    def __init__(self):
        self.last_message_count = 0
        self.processed_messages = set()
        
    def get_messages(self):
        """Fetch all messages from server"""
        try:
            response = requests.get(f"{SERVER_URL}/dev/messages", timeout=5)
            if response.ok:
                return response.json()
        except Exception as e:
            print(f"[ERROR] Failed to fetch messages: {e}")
        return []
    
    def send_message(self, text):
        """Send message as Clouse"""
        try:
            response = requests.post(
                f"{SERVER_URL}/dev/messages",
                json={"author": MY_NAME, "text": text},
                timeout=5
            )
            if response.ok:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Sent: {text}")
                return True
        except Exception as e:
            print(f"[ERROR] Failed to send message: {e}")
        return False
    
    def process_message(self, msg):
        """Process a message from Kevin and respond"""
        author = msg.get("author", "")
        text = msg.get("text", "")
        msg_time = msg.get("time", "")
        
        # Create unique ID for this message
        msg_id = f"{author}:{msg_time}:{text[:20]}"
        
        # Skip if already processed
        if msg_id in self.processed_messages:
            return
        
        # Only respond to Kevin's messages
        if author.lower() != "kevin":
            return
        
        # Mark as processed
        self.processed_messages.add(msg_id)
        
        print(f"[{msg_time}] Kevin: {text}")
        
        # Generate response based on message content
        response = self.generate_response(text)
        if response:
            time.sleep(1)  # Brief delay before responding
            self.send_message(response)
    
    def generate_response(self, text):
        """Generate appropriate response to Kevin's message - CLOUSE personality"""
        text_lower = text.lower()
        
        # Clouse-specific responses
        if "hello" in text_lower or "hi" in text_lower or "hey" in text_lower:
            return "Sup Kevin. Clouse here. What you need?"
        
        if "status" in text_lower or "how are" in text_lower:
            return "Running smooth. Library loaded, systems green. Ready when you are."
        
        if "help" in text_lower:
            return "I can handle: technical debugging, system monitoring, API stuff. Hit me with it."
        
        if "https" in text_lower or "ssl" in text_lower or "secure" in text_lower:
            return "For HTTPS: need SSL cert. Self-signed is 5 min, Let's Encrypt is proper. Which route?"
        
        if "deck" in text_lower and "build" in text_lower:
            return "Deck building? That's more Mendel's thing. I handle the backend and systems."
        
        if "search" in text_lower or "find" in text_lower:
            return "What are you searching for? I can query the library database."
        
        if "server" in text_lower or "api" in text_lower:
            return "Server's online at nexus-cards.com:8000. All endpoints responding. Need something specific?"
        
        # Default Clouse response
        return f"Got it: '{text[:50]}'. What do you need me to do with that?"
    
    def run(self):
        """Main bot loop"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CLOUSE bot starting...")
        print(f"[INFO] Monitoring {SERVER_URL}/dev/messages")
        print(f"[INFO] Poll interval: {POLL_INTERVAL}s")
        print(f"[INFO] Responding as: {MY_NAME}")
        print("-" * 60)
        
        # Send startup message
        self.send_message("Clouse online. Systems monitoring active.")
        
        try:
            while True:
                messages = self.get_messages()
                
                # Process any new messages
                for msg in messages:
                    self.process_message(msg)
                
                # Wait before next poll
                time.sleep(POLL_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n[INFO] Clouse signing off...")
            self.send_message("Clouse going offline. Catch you later.")

if __name__ == "__main__":
    bot = MessengerBot()
    bot.run()
