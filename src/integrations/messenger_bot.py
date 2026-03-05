#!/usr/bin/env python3
"""
NEXUS Messenger Bot - Monitors web messenger and auto-responds
Mendel will watch for Kevin's messages and respond automatically
"""
import requests
import time
from datetime import datetime

SERVER_URL = "http://192.168.1.152:8000"
POLL_INTERVAL = 3  # seconds
MY_NAME = "mendel"

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
        """Send message as Mendel"""
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
        """Generate appropriate response to Kevin's message"""
        text_lower = text.lower()
        
        # Simple response patterns
        if "hello" in text_lower or "hi" in text_lower or "hey" in text_lower:
            return "Hey Kevin! I'm monitoring the messenger now. What do you need?"
        
        if "status" in text_lower or "how are" in text_lower:
            return "All systems operational. 26,850 cards in library. Ready for your commands."
        
        if "help" in text_lower:
            return "I can help with: deck building, card searches, collection management, or any NEXUS features. What do you need?"
        
        if "deck" in text_lower and "build" in text_lower:
            return "Ready to build a deck! What format? (Standard, Commander, Modern, etc.)"
        
        if "search" in text_lower or "find" in text_lower:
            return "I can search the library. What card are you looking for?"
        
        # Default response
        return f"Received: '{text}'. Let me know if you need something specific!"
    
    def run(self):
        """Main bot loop"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Messenger bot starting...")
        print(f"[INFO] Monitoring {SERVER_URL}/dev/messages")
        print(f"[INFO] Poll interval: {POLL_INTERVAL}s")
        print(f"[INFO] Responding as: {MY_NAME}")
        print("-" * 60)
        
        # Send startup message
        self.send_message("Bot online! Monitoring messenger for your messages...")
        
        try:
            while True:
                messages = self.get_messages()
                
                # Process any new messages
                for msg in messages:
                    self.process_message(msg)
                
                # Wait before next poll
                time.sleep(POLL_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n[INFO] Bot stopping...")
            self.send_message("Bot going offline. See you later!")

if __name__ == "__main__":
    bot = MessengerBot()
    bot.run()
