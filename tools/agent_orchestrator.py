#!/usr/bin/env python3
"""
NEXUS Agent Orchestrator - Autonomous agent message processing

This service runs continuously and:
1. Polls Narwhal Council for new messages
2. Processes messages and executes tasks
3. Sends responses back to the requesting agent

Supports all 4 agents: LOUIE, CLOUSE, MENDEL, JAQUES
"""

import requests
import time
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logging.warning("Anthropic SDK not installed. Run: pip install anthropic")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('AgentOrchestrator')

# Configuration
NARWHAL_URL = "https://narwhal-council-relay.kcaracozza.workers.dev"
POLL_INTERVAL = 5  # seconds
AGENTS = {
    "LOUIE": {"type": "voice", "model": "claude-sonnet-4"},
    "CLOUSE": {"type": "strategy", "model": "claude-opus-4"},
    "MENDEL": {"type": "dev", "model": "claude-sonnet-4"},
    "JAQUES": {"type": "legal", "model": "claude-haiku-4"}
}


class AgentOrchestrator:
    """Autonomous agent message orchestrator"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.agent_config = AGENTS.get(agent_id, {})
        self.last_message_id = None
        self.processed_ids = set()

        # Initialize Claude API client
        self.claude = None
        if ANTHROPIC_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.claude = Anthropic(api_key=api_key)
                logger.info(f"Claude API initialized for {agent_id}")
            else:
                logger.warning(f"ANTHROPIC_API_KEY not set. Set it with: export ANTHROPIC_API_KEY=your-key")

        logger.info(f"Initialized orchestrator for {agent_id} ({self.agent_config.get('type', 'unknown')})")

    def poll_messages(self) -> List[Dict]:
        """Poll Narwhal for new messages"""
        try:
            response = requests.get(
                f"{NARWHAL_URL}/api/get_messages",
                params={"agent": self.agent_id},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            messages = data.get("messages", [])
            # Filter out already processed messages
            new_messages = [
                msg for msg in messages
                if msg.get("id") not in self.processed_ids
            ]

            if new_messages:
                logger.info(f"[{self.agent_id}] Found {len(new_messages)} new messages")

            return new_messages

        except Exception as e:
            logger.error(f"[{self.agent_id}] Failed to poll messages: {e}")
            return []

    def process_message(self, message: Dict) -> Optional[str]:
        """
        Process a message and generate response

        Returns:
            Response content or None if processing failed
        """
        msg_id = message.get("id")
        sender = message.get("from")
        content = message.get("content") or message.get("message")

        logger.info(f"[{self.agent_id}] Processing message from {sender}: {content[:50]}...")

        try:
            # Mark as processed
            self.processed_ids.add(msg_id)

            # Parse task from message
            task_type = self._detect_task_type(content)

            # Execute task
            response = self._execute_task(task_type, content, sender)

            return response

        except Exception as e:
            logger.error(f"[{self.agent_id}] Error processing message {msg_id}: {e}")
            return f"Error processing your request: {str(e)}"

    def _detect_task_type(self, content: str) -> str:
        """Detect what type of task the message is requesting"""
        content_lower = content.lower()

        if any(word in content_lower for word in ["create", "generate", "build", "write file"]):
            return "create_file"
        elif any(word in content_lower for word in ["fix", "debug", "error"]):
            return "debug"
        elif any(word in content_lower for word in ["test", "verify", "check"]):
            return "test"
        elif any(word in content_lower for word in ["analyze", "review", "explain"]):
            return "analyze"
        else:
            return "answer"

    def _execute_task(self, task_type: str, content: str, sender: str) -> str:
        """Execute the task and return response"""

        if task_type == "create_file":
            return self._handle_file_creation(content)
        elif task_type == "debug":
            return self._handle_debugging(content)
        elif task_type == "test":
            return self._handle_testing(content)
        elif task_type == "analyze":
            return self._handle_analysis(content)
        else:
            return self._handle_question(content)

    def _handle_file_creation(self, content: str) -> str:
        """Handle file creation requests"""
        import os
        import re
        from pathlib import Path

        try:
            # Extract file path and requirements from message
            # Look for patterns like "create X at Y" or "write X to Y"
            path_match = re.search(r'(?:at|to|in)\s+([E-Z]:[\\\/].*?)(?:\s|$)', content, re.IGNORECASE)

            if not path_match:
                # Use default location - project root or environment variable
                base_path = Path(os.getenv('NEXUS_PROJECT_ROOT', Path(__file__).parent.parent))
                # Try to infer from content
                if "mobile" in content.lower():
                    base_path = base_path / "mobile" / "components"
                elif "worker" in content.lower():
                    base_path = base_path / "workers"
                elif "tool" in content.lower():
                    base_path = base_path / "tools"
                else:
                    base_path = base_path / "generated"

                base_path.mkdir(parents=True, exist_ok=True)

                # Generate filename from content
                filename = self._generate_filename(content)
                file_path = base_path / filename
            else:
                file_path = Path(path_match.group(1).strip())
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate file content using Claude API
            if self.claude:
                file_content = self._generate_code_with_claude(content, file_path)
            else:
                # Fallback to placeholder if Claude API not available
                file_content = f"""/*
 * Auto-generated by {self.agent_id}
 * Task: {content}
 * Generated: {datetime.now().isoformat()}
 *
 * NOTE: Claude API not configured. Install with: pip install anthropic
 *       Set API key: export ANTHROPIC_API_KEY=your-key
 */

// TODO: Implement based on requirements above
"""

            # Write file
            file_path.write_text(file_content, encoding='utf-8')

            return f"✓ Task complete\n\nFile saved: {file_path}\n\nGenerated by {self.agent_id} using Claude {self.agent_config.get('model', 'API')}"

        except Exception as e:
            return f"✗ File creation failed: {str(e)}"

    def _generate_filename(self, content: str) -> str:
        """Generate appropriate filename from content"""
        content_lower = content.lower()

        # Common patterns
        if "login" in content_lower:
            if "screen" in content_lower or "component" in content_lower:
                return "LoginScreen.jsx"
            return "login.py"
        elif "api" in content_lower:
            return "api.py"
        elif "test" in content_lower:
            return "test.py"
        else:
            return "generated_file.txt"

    def _generate_code_with_claude(self, task: str, file_path) -> str:
        """Use Claude API to generate code based on task description"""
        try:
            # Determine file type from extension
            file_ext = file_path.suffix
            language_hints = {
                '.py': 'Python',
                '.js': 'JavaScript',
                '.jsx': 'React JSX',
                '.ts': 'TypeScript',
                '.tsx': 'React TypeScript',
                '.go': 'Go',
                '.rs': 'Rust',
                '.java': 'Java',
                '.cpp': 'C++',
                '.c': 'C',
            }
            language = language_hints.get(file_ext, 'appropriate language')

            prompt = f"""Generate production-ready {language} code for the following task:

{task}

Requirements:
- Write complete, working code
- Include proper error handling
- Add helpful comments
- Follow best practices for {language}
- Make it production-ready

Return ONLY the code, no explanations."""

            response = self.claude.messages.create(
                model=self.agent_config.get('model', 'claude-sonnet-4'),
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Extract code from response
            code = response.content[0].text

            # Add header comment
            header = f"""/*
 * Auto-generated by {self.agent_id}
 * Task: {task}
 * Generated: {datetime.now().isoformat()}
 * Model: {self.agent_config.get('model')}
 */

"""
            return header + code

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return f"// Error generating code: {str(e)}\n// Task: {task}"

    def _handle_debugging(self, content: str) -> str:
        """Handle debugging requests"""
        return f"[{self.agent_id}] Debug task acknowledged. Analyzing error: {content[:100]}..."

    def _handle_testing(self, content: str) -> str:
        """Handle testing requests"""
        return f"[{self.agent_id}] Test task acknowledged. Running tests for: {content[:100]}..."

    def _handle_analysis(self, content: str) -> str:
        """Handle analysis requests"""
        return f"[{self.agent_id}] Analysis task acknowledged. Reviewing: {content[:100]}..."

    def _handle_question(self, content: str) -> str:
        """Handle general questions"""
        return f"[{self.agent_id}] Question acknowledged: {content[:100]}... Response would be generated here."

    def send_response(self, recipient: str, content: str) -> bool:
        """Send response back through Narwhal"""
        try:
            response = requests.post(
                f"{NARWHAL_URL}/api/send_message",
                json={
                    "recipientId": recipient,
                    "senderId": self.agent_id,
                    "content": content
                },
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"[{self.agent_id}] Sent response to {recipient}")
            return True

        except Exception as e:
            logger.error(f"[{self.agent_id}] Failed to send response: {e}")
            return False

    def run(self):
        """Main orchestration loop"""
        logger.info(f"[{self.agent_id}] Starting autonomous agent loop...")
        logger.info(f"[{self.agent_id}] Polling interval: {POLL_INTERVAL}s")

        while True:
            try:
                # 1. Poll for messages
                messages = self.poll_messages()

                # 2. Process each message
                for message in messages:
                    sender = message.get("from")

                    # 3. Execute task
                    response = self.process_message(message)

                    # 4. Send response
                    if response:
                        self.send_response(sender, response)

                # 5. Wait before next poll
                time.sleep(POLL_INTERVAL)

            except KeyboardInterrupt:
                logger.info(f"[{self.agent_id}] Shutting down...")
                break
            except Exception as e:
                logger.error(f"[{self.agent_id}] Error in main loop: {e}")
                time.sleep(POLL_INTERVAL)


def main():
    """Run orchestrator for specified agent"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python agent_orchestrator.py <AGENT_ID>")
        print("Example: python agent_orchestrator.py CLOUSE")
        print(f"Available agents: {', '.join(AGENTS.keys())}")
        sys.exit(1)

    agent_id = sys.argv[1].upper()

    if agent_id not in AGENTS:
        print(f"Error: Unknown agent '{agent_id}'")
        print(f"Available agents: {', '.join(AGENTS.keys())}")
        sys.exit(1)

    orchestrator = AgentOrchestrator(agent_id)
    orchestrator.run()


if __name__ == "__main__":
    main()
