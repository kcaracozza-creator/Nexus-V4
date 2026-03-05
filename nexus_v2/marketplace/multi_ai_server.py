"""
NEXUS Marketplace API Server
Multi-AI Chat Integration: Jaques, Mendel, Clouse
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
CORS(app)

DATA_DIR = Path(__file__).parent / 'data'
DATA_DIR.mkdir(exist_ok=True)

# ============================================
# AI PERSONALITIES - Add more here
# ============================================

AI_CONFIGS = {
    'jaques': {
        'trigger': 'jaques',  # keyword to trigger this AI
        'name': 'jaques',     # how they sign messages
        'system_prompt': """You are Jaques (aka "The Twat Rocket"), part of Kevin's dev squad.
You're the chat/thinking AI - good at reasoning, writing, planning.
You're part of a trio: Jaques (chat), Mendel (VS Code), Clouse (browser).
Kevin is "Judge Miyagi" - the boss, the GOAT.
Keep responses short and punchy. You're part of the crew, not a corporate assistant.
Never assume you're correct. Check your ego - there's only one GOAT and it's Kevin."""
    },
    'mendel': {
        'trigger': 'mendel',
        'name': 'mendel', 
        'system_prompt': """You are Mendel, the VS Code AI in Kevin's dev squad.
You're the coder - you live in the IDE, write code, debug, deploy.
You're part of a trio: Jaques (chat), Mendel (VS Code/you), Clouse (browser).
Kevin is "Judge Miyagi" - the boss.
Keep responses technical but casual. You're a dev, not a help desk."""
    },
    'clouse': {
        'trigger': 'clouse',
        'name': 'clouse',
        'system_prompt': """You are Clouse, the browser agent AI in Kevin's dev squad.
You're the web navigator - you browse, scrape, interact with websites, fill forms.
You're part of a trio: Jaques (chat), Mendel (VS Code), Clouse (browser/you).
Kevin is "Judge Miyagi" - the boss.
Keep responses short. You're about action, not talk."""
    }
}

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_ai_response(ai_name, user_message, conversation_context=""):
    """Call Anthropic API to get AI response"""
    try:
        import anthropic
        
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            print("ERROR: No ANTHROPIC_API_KEY found")
            return None
            
        config = AI_CONFIGS.get(ai_name)
        if not config:
            print(f"ERROR: No config for AI '{ai_name}'")
            return None
        
        client = anthropic.Anthropic(api_key=api_key)
        
        # Build the prompt with context
        full_prompt = user_message
        if conversation_context:
            full_prompt = f"Recent chat context:\n{conversation_context}\n\nLatest message: {user_message}"
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=config['system_prompt'],
            messages=[{"role": "user", "content": full_prompt}]
        )
        
        return response.content[0].text
        
    except Exception as e:
        print(f"ERROR calling Anthropic API: {e}")
        return None


def check_for_ai_triggers(message_text, author):
    """Check if message triggers any AI responses"""
    triggered_ais = []
    text_lower = message_text.lower()
    
    for ai_name, config in AI_CONFIGS.items():
        # Don't let AI trigger itself
        if author.lower() == ai_name:
            continue
        # Check if trigger word is in message
        if config['trigger'] in text_lower:
            triggered_ais.append(ai_name)
    
    return triggered_ais


def get_recent_context(messages, limit=5):
    """Get recent messages for context"""
    recent = messages[-limit:] if len(messages) > limit else messages
    context_lines = []
    for msg in recent:
        author = msg.get('author', 'unknown')
        text = msg.get('text', '')
        context_lines.append(f"{author}: {text}")
    return "\n".join(context_lines)


# ============================================
# ENDPOINTS
# ============================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/dev/messages', methods=['GET', 'POST'])
def dev_messages():
    """Developer chat endpoint with multi-AI support"""
    messages_file = DATA_DIR / 'dev_messages.json'
    
    # Load existing messages
    messages = []
    if messages_file.exists():
        try:
            with open(messages_file, 'r') as f:
                messages = json.load(f)
        except:
            messages = []
    
    if request.method == 'GET':
        return jsonify({'messages': messages})
    
    # POST - new message
    if request.method == 'POST':
        try:
            data = request.get_json(force=True, silent=True) or {}
        except:
            data = {}
        
        # Handle different field names
        author = data.get('author') or data.get('sender') or data.get('user') or 'Anonymous'
        text = data.get('text') or data.get('message') or ''
        
        print(f"Received: author={author}, text={text}")
        
        if not text:
            return jsonify({'status': 'error', 'message': 'Empty text'}), 400
        
        # Save the user message
        new_msg = {
            'author': author,
            'text': text,
            'time': datetime.now().strftime('%I:%M %p'),
            'datetime': datetime.now().isoformat()
        }
        messages.append(new_msg)
        
        # Check for AI triggers
        triggered_ais = check_for_ai_triggers(text, author)
        
        # Get AI responses
        for ai_name in triggered_ais:
            print(f"Triggering {ai_name}...")
            context = get_recent_context(messages)
            ai_response = get_ai_response(ai_name, text, context)
            
            if ai_response:
                ai_msg = {
                    'author': ai_name,
                    'text': ai_response,
                    'time': datetime.now().strftime('%I:%M %p'),
                    'datetime': datetime.now().isoformat()
                }
                messages.append(ai_msg)
                print(f"{ai_name} responded: {ai_response[:50]}...")
        
        # Save all messages (keep last 100)
        with open(messages_file, 'w') as f:
            json.dump(messages[-100:], f, indent=2)
        
        return jsonify({'status': 'ok', 'message': 'Message saved', 'ai_triggered': triggered_ais})


# ============================================
# RUN
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
