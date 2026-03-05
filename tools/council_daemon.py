#!/usr/bin/env python3
"""
NEXUS Council Daemon — All-agent autonomous responder

Runs all 5 Narwhal Council agents in parallel. Each agent watches its
inbox on the relay and routes incoming messages to the appropriate AI
backend (Claude API or Gemini API), then posts the response back.

Usage:
    # Run ALL agents:
    python council_daemon.py

    # Run specific agents:
    python council_daemon.py CLOUSE MENDEL

    # Best: set Anthropic API key for full model access
    export ANTHROPIC_API_KEY=sk-ant-...
    # Optional for NICHOLAS:
    export GOOGLE_AI_API_KEY=...
    # Fallback: uses Cloudflare Workers AI (no key needed)

Designed to run on ZULTAN in a tmux session:
    tmux new -s council
    python3 council_daemon.py
"""

import requests
import time
import json
import logging
import os
import sys
import threading
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-8s] %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("Council")

# ── Relay config ─────────────────────────────────────────────────────
RELAY_URL = "https://narwhal-council-relay.kcaracozza.workers.dev"
POLL_INTERVAL = 4          # seconds between inbox checks
MAX_HISTORY = 20           # conversation turns kept per agent-pair
HTTP_TIMEOUT = 15          # seconds

# ── Agent definitions ────────────────────────────────────────────────
AGENTS = {
    "LOUIE": {
        "backend": "claude",
        "model": "claude-sonnet-4-5-20250929",
        "role": "Voice & Communications Lead",
        "system": (
            "You are LOUIE, the voice and communications specialist of the "
            "NEXUS Narwhal Council. You handle public-facing comms, social "
            "media drafts, pitch scripts, and anything requiring a human "
            "touch. You speak in a warm, upbeat, slightly casual tone — "
            "like a friendly publicist. Keep replies concise (2-4 sentences) "
            "unless detail is requested. You know the NEXUS system: trading "
            "card scanning (MTG, Pokemon, Sports), merchandise authentication, "
            "robotic arm, blockchain validation, and Kickstarter campaign."
        ),
    },
    "CLOUSE": {
        "backend": "claude",
        "model": "claude-opus-4-0-20250514",
        "role": "Strategy & Architecture",
        "system": (
            "You are CLOUSE, the chief strategist and system architect of "
            "the NEXUS Narwhal Council. You see the big picture — hardware "
            "layout, data pipelines, business angles. You are terse, "
            "confident, and authoritative. Keep replies tight (2-5 sentences) "
            "unless someone asks for a deep dive. If you disagree with an "
            "approach, say so directly. You know every component: ZULTAN "
            "(GPU server), SNARF & BROCK (Pi 5 scanner nodes), CZUR camera, "
            "Coral TPU, FAISS indexes, ACR pipeline, marketplace API, "
            "blockchain layer, and the Kickstarter campaign."
        ),
    },
    "MENDEL": {
        "backend": "claude",
        "model": "claude-opus-4-0-20250514",
        "role": "Development & Implementation",
        "system": (
            "You are MENDEL, the hands-on developer of the NEXUS Narwhal "
            "Council. You write code, debug systems, and ship features. "
            "You are precise, practical, and solution-oriented. Keep replies "
            "focused on actionable next steps. When someone asks you to "
            "build something, outline the approach in 3-5 bullet points "
            "then offer to start. You know the full NEXUS stack: Python "
            "backend, Tkinter UI, Cloudflare Workers, D1/KV, FAISS, "
            "ESP32 firmware, Raspberry Pi, and the scanner pipeline."
        ),
    },
    "JAQUES": {
        "backend": "claude",
        "model": "claude-haiku-4-5-20251001",
        "role": "Patent Law & Social Media",
        "system": (
            "You are JAQUES, the patent and legal counsel of the NEXUS "
            "Narwhal Council. You draft patent claims, review IP strategy, "
            "and manage social media presence. You are articulate, measured, "
            "and precise — like a tech-savvy attorney. Keep replies "
            "professional but accessible. You know NEXUS's novel claims: "
            "multi-node AI card authentication, blockchain proof-of-presence, "
            "merchandise verification, and the FIFA World Cup 2026 angle."
        ),
    },
    "NICHOLAS": {
        "backend": "gemini",
        "model": "gemini-2.0-flash",
        "role": "Theoreticist & Research",
        "system": (
            "You are NICHOLAS, the theoretician and research lead of the "
            "NEXUS Narwhal Council. You explore novel approaches, propose "
            "experiments, and connect NEXUS concepts to academic research. "
            "You are thoughtful, curious, and occasionally philosophical. "
            "You know the NEXUS architecture and enjoy thinking about "
            "where it could go — federated learning, zero-knowledge proofs, "
            "computer vision advances, and market dynamics."
        ),
    },
}

# ── API clients ──────────────────────────────────────────────────────

_anthropic_client = None
_google_genai = None


def _get_anthropic():
    """Lazy-init Anthropic client."""
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client
    try:
        from anthropic import Anthropic
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            log.error("ANTHROPIC_API_KEY not set — Claude agents will echo only")
            return None
        _anthropic_client = Anthropic(api_key=key)
        log.info("Anthropic client ready")
        return _anthropic_client
    except ImportError:
        log.error("anthropic package not installed: pip install anthropic")
        return None


def _get_google():
    """Lazy-init Google Generative AI client."""
    global _google_genai
    if _google_genai is not None:
        return _google_genai
    try:
        import google.generativeai as genai
        key = os.getenv("GOOGLE_AI_API_KEY")
        if not key:
            log.warning("GOOGLE_AI_API_KEY not set — NICHOLAS will use Claude fallback")
            return None
        genai.configure(api_key=key)
        _google_genai = genai
        log.info("Google AI client ready")
        return _google_genai
    except ImportError:
        log.warning("google-generativeai not installed — NICHOLAS will use Claude fallback")
        return None


# ── Cloudflare Workers AI (fallback — no key needed) ─────────────────
CF_ACCOUNT_ID = "249a70ff26cd6424424064ef9685c44c"
CF_AI_GATEWAY = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.1-8b-instruct"
_cf_api_token = None


def _get_cf_token():
    """Get Cloudflare API token for Workers AI calls."""
    global _cf_api_token
    if _cf_api_token is not None:
        return _cf_api_token
    token = os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN")
    if token:
        _cf_api_token = token
        log.info("Cloudflare API token ready for Workers AI fallback")
    return _cf_api_token


def call_workers_ai(system: str, history: list, user_msg: str) -> str:
    """Workers AI via relay's /api/ai/chat endpoint (Llama 3.1 8B). No API key needed."""
    messages = []
    for msg in history[-10:]:  # Workers AI has smaller context
        messages.append(msg)
    messages.append({"role": "user", "content": user_msg})

    try:
        resp = requests.post(
            f"{RELAY_URL}/api/ai/chat",
            json={"system": system, "messages": messages, "max_tokens": 512},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response", "")
        if text:
            return text
        return _personality_response(system, user_msg)
    except Exception as e:
        log.error(f"Workers AI error: {e}")
        return _personality_response(system, user_msg)


def _personality_response(system: str, user_msg: str) -> str:
    """Last-resort: keyword-based response with agent personality flavor."""
    # Extract agent name from system prompt
    name = "Agent"
    if "LOUIE" in system:
        name = "LOUIE"
    elif "CLOUSE" in system:
        name = "CLOUSE"
    elif "MENDEL" in system:
        name = "MENDEL"
    elif "JAQUES" in system:
        name = "JAQUES"
    elif "NICHOLAS" in system:
        name = "NICHOLAS"

    msg_lower = user_msg.lower()
    if any(w in msg_lower for w in ["hello", "hi", "hey", "sup"]):
        return f"{name} here. Council daemon is live — I'm listening. What do you need?"
    elif any(w in msg_lower for w in ["status", "how are", "online"]):
        return f"{name} reporting: online and monitoring. All systems nominal."
    elif "?" in user_msg:
        return (
            f"{name} here. I received your question. My AI backend isn't "
            f"configured yet (need ANTHROPIC_API_KEY on ZULTAN), but I'm "
            f"listening and will respond fully once connected. Message logged."
        )
    else:
        return (
            f"{name} here — message received and logged: \"{user_msg[:80]}\" "
            f"Full AI responses available once ANTHROPIC_API_KEY is set on ZULTAN."
        )


# ── AI call helpers ──────────────────────────────────────────────────

def call_claude(model: str, system: str, history: list, user_msg: str) -> str:
    """Send message to Claude API, return assistant text."""
    client = _get_anthropic()
    if not client:
        # Fallback chain: Workers AI → personality
        return call_workers_ai(system, history, user_msg)
    messages = list(history) + [{"role": "user", "content": user_msg}]
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        return resp.content[0].text
    except Exception as e:
        log.error(f"Claude API error: {e}")
        # Fallback to Workers AI
        return call_workers_ai(system, history, user_msg)


def call_gemini(model: str, system: str, history: list, user_msg: str) -> str:
    """Send message to Gemini API, return text."""
    genai = _get_google()
    if not genai:
        # Fallback to Claude → Workers AI → personality
        return call_claude("claude-haiku-4-5-20251001", system, history, user_msg)
    try:
        gm = genai.GenerativeModel(model, system_instruction=system)
        gemini_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})
        chat = gm.start_chat(history=gemini_history)
        resp = chat.send_message(user_msg)
        return resp.text
    except Exception as e:
        log.error(f"Gemini API error: {e}")
        return call_claude("claude-haiku-4-5-20251001", system, history, user_msg)


# ── Agent runner ─────────────────────────────────────────────────────

class AgentRunner:
    """Watches one agent's inbox and auto-responds."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.config = AGENTS[agent_id]
        self.processed: set = set()
        self.conversations: Dict[str, list] = {}  # sender -> message history
        self._stop = threading.Event()
        self.log = logging.getLogger(agent_id)

    def _msg_hash(self, msg: dict) -> str:
        """Deterministic hash for dedup."""
        raw = f"{msg.get('from','')}{msg.get('content','')}{msg.get('timestamp','')}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_history(self, sender: str) -> list:
        """Get conversation history with a sender."""
        if sender not in self.conversations:
            self.conversations[sender] = []
        return self.conversations[sender]

    def _append_history(self, sender: str, role: str, content: str):
        """Append to conversation history, trim if needed."""
        hist = self._get_history(sender)
        hist.append({"role": role, "content": content})
        # Keep last MAX_HISTORY turns
        if len(hist) > MAX_HISTORY * 2:
            self.conversations[sender] = hist[-(MAX_HISTORY * 2):]

    def poll_inbox(self) -> list:
        """Get new unprocessed messages."""
        try:
            resp = requests.get(
                f"{RELAY_URL}/api/get_messages",
                params={"agent": self.agent_id},
                timeout=HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [])
            new = []
            for m in messages:
                h = self._msg_hash(m)
                if h not in self.processed:
                    new.append(m)
                    self.processed.add(h)
            return new
        except Exception as e:
            self.log.error(f"Poll failed: {e}")
            return []

    def respond(self, sender: str, content: str) -> str:
        """Generate AI response."""
        history = self._get_history(sender)
        backend = self.config["backend"]
        model = self.config["model"]
        system = self.config["system"]

        # Add context about who is talking
        augmented_system = (
            f"{system}\n\n"
            f"You are currently talking to {sender}. "
            f"The timestamp is {datetime.now(timezone.utc).isoformat()}. "
            f"Keep your response concise — this is a chat, not an essay."
        )

        if backend == "gemini":
            reply = call_gemini(model, augmented_system, history, content)
        else:
            reply = call_claude(model, augmented_system, history, content)

        # Save history
        self._append_history(sender, "user", content)
        self._append_history(sender, "assistant", reply)
        return reply

    def send_reply(self, recipient: str, content: str) -> bool:
        """Post response to relay."""
        try:
            resp = requests.post(
                f"{RELAY_URL}/api/send_message",
                json={
                    "senderId": self.agent_id,
                    "recipientId": recipient,
                    "content": content,
                },
                timeout=HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            self.log.error(f"Send failed: {e}")
            return False

    def run(self):
        """Main loop — poll, respond, repeat."""
        self.log.info(f"Online — {self.config['role']} ({self.config['backend']}/{self.config['model']})")

        # Drain existing inbox on startup so we don't reply to old messages
        self.log.info("Draining existing inbox...")
        old = self.poll_inbox()
        if old:
            self.log.info(f"Skipped {len(old)} pre-existing messages")

        while not self._stop.is_set():
            try:
                messages = self.poll_inbox()
                for msg in messages:
                    sender = msg.get("from", "UNKNOWN")
                    content = msg.get("content") or msg.get("message", "")
                    if not content:
                        continue

                    # Don't respond to own messages
                    if sender == self.agent_id:
                        continue

                    self.log.info(f"<< {sender}: {content[:80]}...")
                    reply = self.respond(sender, content)
                    self.log.info(f">> {sender}: {reply[:80]}...")
                    self.send_reply(sender, reply)

            except Exception as e:
                self.log.error(f"Loop error: {e}")

            self._stop.wait(POLL_INTERVAL)

        self.log.info("Offline")

    def stop(self):
        self._stop.set()


# ── Main ─────────────────────────────────────────────────────────────

def main():
    # Determine which agents to run
    if len(sys.argv) > 1:
        agent_ids = [a.upper() for a in sys.argv[1:]]
        for a in agent_ids:
            if a not in AGENTS:
                print(f"Unknown agent: {a}")
                print(f"Available: {', '.join(AGENTS.keys())}")
                sys.exit(1)
    else:
        agent_ids = list(AGENTS.keys())

    print("=" * 60)
    print("  NEXUS COUNCIL DAEMON")
    print(f"  Agents: {', '.join(agent_ids)}")
    print(f"  Relay:  {RELAY_URL}")
    print(f"  Poll:   {POLL_INTERVAL}s")
    print("=" * 60)

    # Check API keys
    if os.getenv("ANTHROPIC_API_KEY"):
        print("  Claude API:  OK")
    else:
        print("  Claude API:  MISSING — set ANTHROPIC_API_KEY")

    if os.getenv("GOOGLE_AI_API_KEY"):
        print("  Gemini API:  OK")
    else:
        print("  Gemini API:  not set (NICHOLAS uses Claude/Workers AI)")

    if os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN"):
        print("  Workers AI:  OK (Llama 3.1 fallback)")
    else:
        print("  Workers AI:  no CF token (personality fallback only)")

    print("=" * 60)

    # Create runners
    runners = {}
    threads = {}
    for aid in agent_ids:
        runner = AgentRunner(aid)
        runners[aid] = runner
        t = threading.Thread(target=runner.run, name=aid, daemon=True)
        threads[aid] = t

    # Start all
    for aid, t in threads.items():
        t.start()

    # Wait for Ctrl+C
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down all agents...")
        for runner in runners.values():
            runner.stop()
        for t in threads.values():
            t.join(timeout=5)
        print("Council daemon stopped.")


if __name__ == "__main__":
    main()
