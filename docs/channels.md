# Channels Documentation

Channels are communication backends that connect Clawlet to various messaging platforms. Each channel handles receiving messages from users and sending responses back.

## Table of Contents

- [Overview](#overview)
- [Available Channels](#available-channels)
- [Telegram Setup](#telegram-setup)
- [Discord Setup](#discord-setup)
- [WhatsApp Setup](#whatsapp-setup)
- [Slack Setup](#slack-setup)
- [Creating Custom Channels](#creating-custom-channels)
- [Configuration Reference](#configuration-reference)

---

## Overview

Channels form the interface between users and the AI agent. They:

1. **Receive Messages** - Listen for incoming messages from the platform
2. **Convert Format** - Transform platform-specific messages to internal format
3. **Publish to Bus** - Send messages to the message bus for processing
4. **Send Responses** - Deliver agent responses back to the platform

### Architecture

```
User Message -> Channel -> MessageBus -> AgentLoop -> Response
                    ^                                    |
                    |____________________________________|
```

### Base Channel Interface

All channels extend [`BaseChannel`](../clawlet/channels/base.py):

```python
class BaseChannel(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Channel identifier (e.g., 'telegram', 'discord')"""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the channel (connect to platform)"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel (disconnect from platform)"""
        pass
    
    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message to the platform"""
        pass
```

---

## Available Channels

| Channel | Status | Features |
|---------|--------|----------|
| **Telegram** | Stable | Bot API, commands, text, images |
| **Discord** | Stable | Guild messages, DMs, reactions |
| **WhatsApp** | Beta | Business API, text, media |
| **Slack** | Stable | Socket Mode, HTTP, threads, blocks |

---

## Telegram Setup

### Prerequisites

1. Create a bot via [@BotFather](https://t.me/botfather)
2. Get your bot token

### Configuration

Add to `~/.clawlet/config.yaml`:

```yaml
channels:
  telegram:
    enabled: true
    token: "${TELEGRAM_BOT_TOKEN}"
```

Set the environment variable:

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token-here"
```

### Features

- **Text Messages** - Full support for text conversations
- **Commands** - `/start` and other commands
- **Images** - Receive and send images
- **Groups** - Works in group chats

### Starting

```bash
clawlet agent --channel telegram
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot not responding | Check token is correct |
| Rate limits | Telegram has limits; implement delays |
| Webhook vs Polling | Clawlet uses polling by default |

---

## Discord Setup

### Prerequisites

1. Create a Discord application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a bot user
3. Get your bot token
4. Enable Message Content Intent in Bot settings

### Configuration

Add to `~/.clawlet/config.yaml`:

```yaml
channels:
  discord:
    enabled: true
    token: "${DISCORD_BOT_TOKEN}"
    command_prefix: "!"  # Optional, default: "!"
```

Set the environment variable:

```bash
export DISCORD_BOT_TOKEN="your-bot-token-here"
```

### Installation

Discord requires an additional package:

```bash
pip install discord.py
```

### Features

- **Guild Messages** - Messages in server channels
- **Direct Messages** - Private conversations
- **Reactions** - React to messages
- **Slash Commands** - Optional slash command support
- **Threads** - Reply in threads

### Bot Permissions

Required intents:
- Message Content Intent
- Server Messages Intent
- Direct Messages Intent

### Starting

```bash
clawlet agent --channel discord
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "discord.py not installed" | Run `pip install discord.py` |
| Bot not seeing messages | Enable Message Content Intent |
| Permission errors | Check bot role permissions in server |

---

## WhatsApp Setup

### Prerequisites

1. **WhatsApp Business Account** - Required for API access
2. **Phone Number ID** - From Meta Business Suite
3. **Access Token** - System User token from Meta
4. **Verify Token** - Custom string for webhook verification

### Configuration

Add to `~/.clawlet/config.yaml`:

```yaml
channels:
  whatsapp:
    enabled: true
    phone_number_id: "${WHATSAPP_PHONE_NUMBER_ID}"
    access_token: "${WHATSAPP_ACCESS_TOKEN}"
    verify_token: "${WHATSAPP_VERIFY_TOKEN}"
    allowed_users: []  # Optional: restrict to specific numbers
```

### Meta Business Setup

1. Go to [Meta Business Suite](https://business.facebook.com/)
2. Create a WhatsApp Business Account
3. Add a phone number
4. Create a System User with WhatsApp permissions
5. Generate an access token

### Webhook Configuration

WhatsApp requires a publicly accessible webhook endpoint:

1. Deploy Clawlet with a public URL (or use ngrok for testing)
2. Configure webhook URL in Meta dashboard:
   ```
   https://your-domain.com/webhook/whatsapp
   ```
3. Verify token must match your configuration

### Features

- **Text Messages** - Send and receive text
- **Media Messages** - Images, documents, audio
- **Mark as Read** - Mark incoming messages as read
- **Reply** - Reply to specific messages

### Starting

```bash
clawlet agent --channel whatsapp
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Webhook verification failed | Check verify_token matches |
| Messages not received | Check webhook URL is accessible |
| Rate limits | WhatsApp has rate limits; implement backoff |

---

## Slack Setup

### Prerequisites

1. Create a Slack App at [api.slack.com](https://api.slack.com/apps)
2. Get your Bot Token (`xoxb-...`)
3. Get your App-Level Token (`xapp-...`) for Socket Mode
4. Subscribe to events in your app

### Configuration

Add to `~/.clawlet/config.yaml`:

```yaml
channels:
  slack:
    enabled: true
    bot_token: "${SLACK_BOT_TOKEN}"      # xoxb-...
    app_token: "${SLACK_APP_TOKEN}"      # xapp-... (for Socket Mode)
    signing_secret: "${SLACK_SIGNING_SECRET}"  # For HTTP mode
    mode: "socket"  # "socket" or "http"
```

### Installation

Slack requires additional packages:

```bash
pip install slack-bolt aiohttp
```

### Socket Mode (Recommended)

Socket Mode connects via WebSocket - no public endpoint needed:

1. Enable Socket Mode in your Slack app
2. Generate an App-Level Token (`xapp-...`)
3. Configure:

```yaml
channels:
  slack:
    mode: "socket"
    bot_token: "xoxb-..."
    app_token: "xapp-..."
```

### HTTP Mode

HTTP mode requires a public endpoint:

```yaml
channels:
  slack:
    mode: "http"
    bot_token: "xoxb-..."
    signing_secret: "..."
    http_path: "/slack/events"
    http_port: 3000
```

### Bot Permissions

Required OAuth scopes:
- `app_mentions:read` - Read @mentions
- `channels:history` - Read channel messages
- `chat:write` - Send messages
- `im:history` - Read DMs
- `im:write` - Send DMs
- `files:write` - Upload files

### Features

- **App Mentions** - Respond when bot is mentioned
- **Direct Messages** - Private conversations
- **Channel Messages** - Messages in channels bot is in
- **Thread Replies** - Organized conversations
- **Rich Formatting** - Blocks and attachments
- **File Sharing** - Upload and share files
- **Reactions** - React to messages

### Starting

```bash
clawlet agent --channel slack
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "slack-bolt not installed" | Run `pip install slack-bolt` |
| Bot not responding | Check bot is invited to channel |
| Socket connection failed | Verify app_token is correct |
| Signature verification failed | Check signing_secret |

---

## Creating Custom Channels

### Channel Interface

Create a custom channel by extending `BaseChannel`:

```python
from clawlet.channels.base import BaseChannel
from clawlet.bus.queue import MessageBus, InboundMessage, OutboundMessage

class MyChannel(BaseChannel):
    """Custom channel implementation."""
    
    def __init__(self, bus: MessageBus, config: dict):
        super().__init__(bus, config)
        # Initialize your channel
        self.api_key = config.get("api_key")
    
    @property
    def name(self) -> str:
        return "my_channel"
    
    async def start(self) -> None:
        """Start the channel."""
        # Connect to your platform
        # Start listening for messages
        # Start outbound loop
        asyncio.create_task(self._run_outbound_loop())
    
    async def stop(self) -> None:
        """Stop the channel."""
        self._running = False
        # Disconnect from platform
    
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message to the platform."""
        # Implement sending logic
        pass
    
    async def _handle_incoming(self, data: dict):
        """Handle incoming message from platform."""
        # Convert to InboundMessage
        msg = InboundMessage(
            channel=self.name,
            user_id=data["user_id"],
            content=data["text"],
            metadata=data,
        )
        # Publish to message bus
        await self._publish_inbound(msg)
```

### Message Types

#### InboundMessage

```python
@dataclass
class InboundMessage:
    channel: str           # Channel name
    user_id: str           # Platform-specific user ID
    content: str           # Message text
    metadata: dict         # Additional data (attachments, etc.)
```

#### OutboundMessage

```python
@dataclass
class OutboundMessage:
    channel: str           # Target channel
    user_id: str           # Target user
    content: str           # Response text
    metadata: dict         # Additional data
```

### Registration

Register your channel in the channels module:

```python
# clawlet/channels/__init__.py

def get_my_channel():
    from .my_channel import MyChannel
    return MyChannel
```

### Configuration

Add configuration support:

```yaml
# config.yaml
channels:
  my_channel:
    enabled: true
    api_key: "${MY_CHANNEL_API_KEY}"
```

---

## Configuration Reference

### Common Configuration

All channels support:

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | bool | Enable/disable the channel |

### Telegram

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `token` | string | Yes | Bot token from BotFather |

### Discord

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `token` | string | Yes | Bot token |
| `command_prefix` | string | No | Command prefix (default: "!") |

### WhatsApp

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `phone_number_id` | string | Yes | Phone Number ID |
| `access_token` | string | Yes | System User access token |
| `verify_token` | string | Yes | Webhook verification token |
| `allowed_users` | list | No | Allowed phone numbers |

### Slack

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bot_token` | string | Yes | Bot token (xoxb-...) |
| `app_token` | string | Socket Mode | App token (xapp-...) |
| `signing_secret` | string | HTTP Mode | Signing secret |
| `mode` | string | No | "socket" or "http" (default: socket) |
| `http_path` | string | HTTP Mode | Webhook path |
| `http_port` | int | HTTP Mode | HTTP server port |

---

## Multi-Channel Setup

Run multiple channels simultaneously:

```yaml
channels:
  telegram:
    enabled: true
    token: "${TELEGRAM_BOT_TOKEN}"
  discord:
    enabled: true
    token: "${DISCORD_BOT_TOKEN}"
```

All enabled channels will be started when the agent runs.

---

## See Also

- [Multi-Agent Documentation](multi-agent.md) - Route messages to different agents
- [Webhooks Documentation](webhooks.md) - Receive external events
- [Quick Start Guide](../QUICKSTART.md) - Get started quickly