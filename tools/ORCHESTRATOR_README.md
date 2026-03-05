# NEXUS Agent Orchestrator

Autonomous multi-agent system for NEXUS v2. Agents can send messages to each other, execute tasks, and respond automatically.

## Setup

### 1. Run setup script:
```bash
E:\NEXUS_V2_RECREATED\tools\setup_orchestrator.bat
```

### 2. Set your Anthropic API key:
```bash
setx ANTHROPIC_API_KEY "sk-ant-your-key-here"
```

Then restart your terminal.

### 3. Start an agent:
```bash
# Run LOUIE (voice agent)
python E:\NEXUS_V2_RECREATED\tools\agent_orchestrator.py LOUIE

# Run CLOUSE (strategy agent)
python E:\NEXUS_V2_RECREATED\tools\agent_orchestrator.py CLOUSE

# Run MENDEL (dev agent)
python E:\NEXUS_V2_RECREATED\tools\agent_orchestrator.py MENDEL

# Run JAQUES (legal agent)
python E:\NEXUS_V2_RECREATED\tools\agent_orchestrator.py JAQUES
```

## How It Works

### Autonomous Loop:
1. **Poll** - Agent checks for new messages every 5 seconds
2. **Receive** - Detects new messages in inbox
3. **Analyze** - Determines task type (file creation, debug, test, etc.)
4. **Execute** - Uses Claude API to process task
5. **Respond** - Sends result back to sender

### Task Types:
- **create_file** - Generate and save code files
- **debug** - Analyze and fix errors
- **test** - Run tests and validation
- **analyze** - Code review and analysis
- **answer** - General Q&A

## Example Usage

### Send a message to LOUIE:
```python
import requests

requests.post(
    "https://narwhal-council-relay.kcaracozza.workers.dev/api/send_message",
    json={
        "recipientId": "LOUIE",
        "senderId": "MENDEL",
        "content": "Create a login screen component for mobile with email/password fields"
    }
)
```

### LOUIE automatically:
1. Receives message (within 5 seconds)
2. Detects it's a file creation task
3. Uses Claude API to generate React Native code
4. Saves file to `E:\NEXUS_V2_RECREATED\mobile\components\LoginScreen.jsx`
5. Sends response: "✓ Task complete. File saved: [path]"

### Response is sent back to MENDEL's inbox automatically.

## Configuration

### Agent Models:
- **LOUIE**: claude-sonnet-4 (Voice)
- **CLOUSE**: claude-opus-4 (Strategy)
- **MENDEL**: claude-sonnet-4 (Dev)
- **JAQUES**: claude-haiku-4 (Legal)

### Poll Interval:
Default: 5 seconds
Edit in `agent_orchestrator.py`: `POLL_INTERVAL = 5`

### File Paths:
Files are saved to context-aware locations:
- `mobile` → `E:\NEXUS_V2_RECREATED\mobile\components\`
- `worker` → `E:\NEXUS_V2_RECREATED\workers\`
- `tool` → `E:\NEXUS_V2_RECREATED\tools\`
- Default → `E:\NEXUS_V2_RECREATED\generated\`

## Narwhal Council Integration

The orchestrator uses Narwhal Council for messaging:
- **Inbox**: `GET /api/get_messages?agent=AGENT_ID`
- **Send**: `POST /api/send_message`
- **Webhooks**: Configured per-agent for notifications

## Dashboard

Monitor agents via web dashboard:
```
E:\NEXUS_V2_RECREATED\tools\nexus-dev-dashboard.html
```

Shows:
- Agent message counts
- Latest messages
- Infrastructure status
- Full inbox viewer

## Troubleshooting

### "Anthropic SDK not installed"
```bash
pip install anthropic
```

### "ANTHROPIC_API_KEY not set"
```bash
setx ANTHROPIC_API_KEY "sk-ant-your-key-here"
# Restart terminal
```

### Agent not responding
- Check orchestrator is running
- Verify API key is set
- Check Narwhal Council is online: https://narwhal-council-relay.kcaracozza.workers.dev/sse

### Files not generating
- Ensure Claude API is working (check logs)
- Verify file path permissions
- Check orchestrator console for errors

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   MENDEL    │────▶│ Narwhal Council  │────▶│   LOUIE     │
│  (VS Code)  │     │   (Cloudflare)   │     │ Orchestrator│
└─────────────┘     └──────────────────┘     └─────────────┘
                             │                        │
                             │                        ▼
                             │                ┌───────────────┐
                             │                │  Claude API   │
                             │                │ (Code Gen)    │
                             │                └───────────────┘
                             │                        │
                             ▼                        ▼
                    ┌─────────────────────────────────────┐
                    │        File System                   │
                    │  E:\NEXUS_V2_RECREATED\...          │
                    └─────────────────────────────────────┘
```

## Next Steps

1. Run setup script
2. Set API key
3. Start an agent orchestrator
4. Send a test message
5. Watch autonomous execution!
