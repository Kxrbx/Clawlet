# Multi-Agent Documentation

Clawlet supports running multiple agents, each with its own workspace, identity, and configuration. This enables scenarios like personal assistants, team bots, and specialized agents.

## Table of Contents

- [Overview](#overview)
- [Workspace Management](#workspace-management)
- [Routing Rules](#routing-rules)
- [CLI Commands](#cli-commands)
- [Use Cases](#use-cases)
- [Configuration Reference](#configuration-reference)

---

## Overview

Multi-agent support allows you to:

- **Separate Contexts** - Each agent has its own memory and identity
- **Specialize Agents** - Configure agents for specific tasks
- **Route Messages** - Automatically route messages to the right agent
- **Isolate Workspaces** - Separate configuration and data

### Architecture

```
Message -> AgentRouter -> RouteRule Match -> AgentLoop (Workspace)
                                     |
                                     +-> AgentLoop (Workspace)
                                     |
                                     +-> AgentLoop (Workspace)
```

### Components

| Component | Purpose |
|-----------|---------|
| `Workspace` | Isolated agent environment |
| `AgentRouter` | Routes messages to agents |
| `RouteRule` | Defines routing criteria |
| `AgentConfig` | Agent configuration |

---

## Workspace Management

Each workspace is a self-contained environment:

### Workspace Structure

```
~/.clawlet/
  workspaces/
    personal/
      config.yaml      # Workspace-specific config
      SOUL.md          # Agent personality
      USER.md          # User information
      MEMORY.md        # Long-term memory
      HEARTBEAT.md     # Scheduled tasks
      memory/
        clawlet.db     # Memory database
    work/
      config.yaml
      SOUL.md
      USER.md
      ...
```

### Creating a Workspace

```bash
# Create a new workspace
clawlet workspace create personal

# Create with specific settings
clawlet workspace create work --agent-name "WorkBot" --user-name "Team"
```

### Workspace Contents

| File | Purpose |
|------|---------|
| `config.yaml` | Provider, channels, tools config |
| `SOUL.md` | Agent personality and capabilities |
| `USER.md` | User information and preferences |
| `MEMORY.md` | Long-term memory storage |
| `HEARTBEAT.md` | Periodic task definitions |
| `memory/clawlet.db` | SQLite memory database |

### Listing Workspaces

```bash
clawlet workspace list
```

Output:
```
Workspaces:
  * personal (active)
    - work
    - assistant
```

### Switching Workspaces

```bash
clawlet workspace switch work
```

### Deleting a Workspace

```bash
# Delete a workspace (with confirmation)
clawlet workspace delete old_workspace
```

---

## Routing Rules

Routing rules determine which agent handles each message.

### Rule Structure

A rule matches if ALL specified conditions match (AND logic):

```yaml
routes:
  - agent: personal
    channel: telegram
    user_id: "123456789"
    priority: 10
```

### Rule Fields

| Field | Type | Description |
|-------|------|-------------|
| `agent` | string | Target agent ID |
| `channel` | string | Match channel name |
| `user_id` | string | Match specific user |
| `workspace` | string | Match workspace name |
| `pattern` | regex | Match message content |
| `priority` | int | Higher = checked first |

### Priority Order

Rules are checked in priority order (highest first). The first matching rule wins.

```yaml
routes:
  # High priority: Direct message from owner
  - agent: personal
    channel: telegram
    user_id: "123456789"
    priority: 100
  
  # Medium priority: Messages containing "work"
  - agent: work
    pattern: "\\bwork\\b"
    priority: 50
  
  # Low priority: Default fallback
  - agent: general
    priority: 0
```

### Pattern Matching

Use regex patterns to match message content:

```yaml
routes:
  # Route calendar-related messages
  - agent: scheduler
    pattern: "(meeting|calendar|schedule|event)"
    priority: 30
  
  # Route code-related messages
  - agent: coder
    pattern: "(code|debug|function|error|bug)"
    priority: 30
```

### Default Route

Create a catch-all route with low priority:

```yaml
routes:
  - agent: general
    priority: 0
```

---

## CLI Commands

### Workspace Commands

```bash
# List workspaces
clawlet workspace list

# Create workspace
clawlet workspace create <name>

# Switch active workspace
clawlet workspace switch <name>

# Delete workspace
clawlet workspace delete <name>

# Show workspace info
clawlet workspace info <name>
```

### Agent Commands

```bash
# Start specific agent
clawlet agent --workspace personal

# Start multiple agents
clawlet agent --workspace personal --workspace work

# Start all configured agents
clawlet agent --all-workspaces
```

### Router Commands

```bash
# Show routing rules
clawlet routes list

# Add a route
clawlet routes add --agent personal --channel telegram --priority 10

# Remove a route
clawlet routes remove <index>

# Clear all routes
clawlet routes clear
```

---

## Use Cases

### Personal + Work Separation

Separate your personal assistant from work-related tasks:

```yaml
# config.yaml
workspaces:
  personal:
    enabled: true
    description: "Personal assistant for daily life"
  work:
    enabled: true
    description: "Work assistant for professional tasks"

routes:
  - agent: personal
    channel: telegram
    user_id: "${PERSONAL_TELEGRAM_ID}"
    priority: 100
  
  - agent: work
    channel: slack
    priority: 50
```

### Team Bot with Specialized Agents

Different agents for different team functions:

```yaml
workspaces:
  support:
    enabled: true
    description: "Customer support agent"
  dev:
    enabled: true
    description: "Developer assistant"
  general:
    enabled: true
    description: "General team assistant"

routes:
  # Support channel -> support agent
  - agent: support
    channel: slack
    pattern: "#support"
    priority: 50
  
  # Dev channel -> dev agent
  - agent: dev
    channel: slack
    pattern: "#dev|#engineering"
    priority: 50
  
  # Default -> general agent
  - agent: general
    priority: 0
```

### Channel-Specific Agents

Different agents for different platforms:

```yaml
workspaces:
  telegram_bot:
    enabled: true
  discord_bot:
    enabled: true
  slack_bot:
    enabled: true

routes:
  - agent: telegram_bot
    channel: telegram
    priority: 10
  
  - agent: discord_bot
    channel: discord
    priority: 10
  
  - agent: slack_bot
    channel: slack
    priority: 10
```

### User-Specific Agents

Personal agents for different users:

```yaml
workspaces:
  alice:
    enabled: true
  bob:
    enabled: true

routes:
  - agent: alice
    user_id: "alice_telegram_id"
    priority: 100
  
  - agent: bob
    user_id: "bob_telegram_id"
    priority: 100
```

### Topic-Based Routing

Route based on message content:

```yaml
workspaces:
  calendar:
    enabled: true
    skills:
      - calendar
  email:
    enabled: true
    skills:
      - email
  notes:
    enabled: true
    skills:
      - notes

routes:
  - agent: calendar
    pattern: "(meeting|schedule|calendar|event|appointment)"
    priority: 30
  
  - agent: email
    pattern: "(email|mail|send.*message)"
    priority: 30
  
  - agent: notes
    pattern: "(note|remember|remind|todo)"
    priority: 30
```

---

## Configuration Reference

### Multi-Agent Configuration

```yaml
# ~/.clawlet/config.yaml

# Workspace definitions
workspaces:
  personal:
    enabled: true
    description: "Personal assistant"
    path: "~/.clawlet/workspaces/personal"
  
  work:
    enabled: true
    description: "Work assistant"
    path: "~/.clawlet/workspaces/work"

# Routing rules
routes:
  - agent: personal
    channel: telegram
    user_id: "123456789"
    priority: 100
  
  - agent: work
    channel: slack
    priority: 50
  
  - agent: personal
    priority: 0  # Default fallback
```

### Workspace Configuration

Each workspace has its own `config.yaml`:

```yaml
# ~/.clawlet/workspaces/personal/config.yaml

# Provider configuration
provider:
  primary: openai
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4o"

# Channel configuration (can override global)
channels:
  telegram:
    enabled: true

# Skills for this workspace
skills:
  calendar:
    enabled: true
  notes:
    enabled: true

# Workspace-specific settings
workspace:
  name: "personal"
  allowed_directories:
    - "~/Documents"
    - "~/Desktop"
```

### Route Rule Configuration

```yaml
routes:
  - agent: string          # Required: Target agent ID
    channel: string        # Optional: Match channel
    user_id: string        # Optional: Match user ID
    workspace: string      # Optional: Match workspace
    pattern: string        # Optional: Regex pattern
    priority: int          # Optional: Priority (default: 0)
```

---

## Best Practices

### 1. Clear Separation

Give each workspace a distinct purpose:

```yaml
workspaces:
  personal:
    description: "Personal life management"
  work:
    description: "Professional tasks and projects"
  finance:
    description: "Financial tracking and budgets"
```

### 2. Priority Hierarchy

Use a consistent priority scale:

| Priority | Use Case |
|----------|----------|
| 100+ | User-specific routes |
| 50-99 | Channel-specific routes |
| 10-49 | Pattern-based routes |
| 0-9 | Default/fallback routes |

### 3. Fallback Agent

Always have a default route:

```yaml
routes:
  # ... specific routes ...
  
  - agent: general
    priority: 0
```

### 4. Workspace Isolation

Configure workspace-specific settings:

```yaml
# In workspace config.yaml
workspace:
  allowed_directories:
    - "~/Work/Projects"  # Only work directories
```

### 5. Memory Separation

Each workspace has its own memory database, ensuring context isolation.

---

## Troubleshooting

### Message Not Routed

1. Check route priority order
2. Verify rule conditions match
3. Check agent is enabled
4. Review router logs

### Wrong Agent Responds

1. Check for conflicting rules
2. Verify priority values
3. Test pattern matching

### Workspace Not Found

1. Verify workspace path exists
2. Check workspace is enabled
3. Run `clawlet workspace list`

### Debug Mode

Enable router debug logging:

```yaml
logging:
  router: DEBUG
```

---

## See Also

- [Channels Documentation](channels.md) - Configure messaging platforms
- [Skills Documentation](skills.md) - Add capabilities to agents
- [Scheduling Documentation](scheduling.md) - Schedule agent tasks
- [Configuration Guide](../QUICKSTART.md) - Basic configuration