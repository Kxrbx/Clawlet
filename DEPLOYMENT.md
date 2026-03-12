# Deployment Guide

This guide describes a generic production deployment flow for Clawlet after cloning the repository.

## Overview

Clawlet can be deployed in a minimal setup with:

- the `clawlet` Python runtime
- an optional database backend (`sqlite` by default, `postgres` optional)
- optional channels such as Telegram, Discord, Slack, or WhatsApp
- optional dashboard/frontend components if you use them

## 1. Clone And Install

```bash
git clone https://github.com/Kxrbx/Clawlet.git
cd Clawlet

python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optional dashboard/frontend dependencies:

```bash
pip install -e ".[dashboard]"
cd dashboard
npm install
```

## 2. Initialize Workspace

Create a clean local workspace and config:

```bash
clawlet init
# or
clawlet onboard
```

This creates the local runtime workspace under `~/.clawlet/` by default.

## 3. Configure Runtime

Edit your generated config:

```bash
$EDITOR ~/.clawlet/config.yaml
```

Recommended baseline:

```yaml
provider:
  primary: openrouter
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    model: "anthropic/claude-sonnet-4"

runtime:
  engine: python

heartbeat:
  enabled: true
  interval_minutes: 30
  quiet_hours_start: 0
  quiet_hours_end: 0
  target: "last"
```

## 4. Start The Agent

```bash
clawlet agent
```

Channel-specific examples:

```bash
# Use these only after configuring the channel in config.yaml
clawlet agent --channel telegram
clawlet agent --channel discord
```

## 5. Heartbeat Operations

Heartbeat is driven by `HEARTBEAT.md` in the workspace.

Useful commands:

```bash
clawlet heartbeat status
clawlet heartbeat last
clawlet heartbeat enable
clawlet heartbeat disable
```

Important behavior:

- empty/comment-only `HEARTBEAT.md` means no heartbeat action is taken
- heartbeat state is persisted under `memory/heartbeat-state.json` in the workspace
- runtime replay/checkpoints are stored under `.runtime/`

## 6. Logs And Runtime State

Useful commands:

```bash
clawlet logs
clawlet replay <run_id>
clawlet recovery list
```

Typical local runtime files:

- `~/.clawlet/config.yaml`
- `~/.clawlet/HEARTBEAT.md`
- `~/.clawlet/MEMORY.md`
- `~/.clawlet/memory/heartbeat-state.json`
- `~/.clawlet/.runtime/`

## 7. Optional Service Management

For long-running deployment, use a process manager such as:

- `systemd`
- `supervisord`
- `pm2`
- Docker / Docker Compose

Example `systemd` unit shape:

```ini
[Unit]
Description=Clawlet Agent
After=network.target

[Service]
WorkingDirectory=/path/to/Clawlet
ExecStart=/path/to/Clawlet/.venv/bin/clawlet agent
Restart=always
User=your-user
Environment=OPENROUTER_API_KEY=...

[Install]
WantedBy=multi-user.target
```

## 8. Pre-Deployment Checklist

- provider API keys configured
- channel tokens configured if channels are enabled
- `clawlet validate` passes
- `clawlet health` passes
- `HEARTBEAT.md` reviewed before enabling autonomous background work
- log/replay retention reviewed for your environment

## 9. Notes

- Repository contents are source code and docs only; local runtime state should live in the workspace, not in the repository checkout.
- Do not commit generated runtime artifacts such as `.runtime/`, local databases, or workspace memory files back into the repo.
