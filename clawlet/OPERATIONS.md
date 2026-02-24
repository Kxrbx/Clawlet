# Clawlet Operations Guide

_How to run, monitor, debug, and maintain a Clawlet agent._

---

## Quick Start

1. **Install dependencies**

```bash
cd /path/to/clawlet
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-core.txt
```

2. **Create workspace** (if not already)

```bash
clawlet init   # or: clawlet onboard
```

3. **Edit config**

```bash
nano ~/.clawlet/config.yaml
```

Set your `OPENROUTER_API_KEY` and enable desired channels (Telegram token, etc.).

4. **Start the agent**

```bash
clawlet agent
```

---

## Starting & Stopping

### Manual (foreground)

```bash
source .venv/bin/activate
clawlet agent
```

Use `Ctrl+C` to stop (graceful shutdown).

### Systemd service (recommended for production)

Create `/etc/systemd/system/clawlet.service`:

```ini
[Unit]
Description=Clawlet AI Agent
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/clawlet
Environment="PATH=/path/to/clawlet/.venv/bin"
Environment="OPENROUTER_API_KEY=your_key_here"
ExecStart=/path/to/clawlet/.venv/bin/clawlet agent
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable clawlet
sudo systemctl start clawlet
sudo systemctl status clawlet
```

Logs:

```bash
sudo journalctl -u clawlet -f
```

---

## Docker Deployment (without dashboard)

Build image:

```bash
docker build -t clawlet:latest -f Dockerfile .
```

Run:

```bash
docker run -d \
  --name clawlet \
  -v ~/.clawlet:/root/.clawlet \
  -e OPENROUTER_API_KEY=your_key \
  -e TZ=Europe/Paris \
  clawlet:latest
```

Using docker‑compose (`docker-compose.yml`):

```bash
docker-compose up -d
docker-compose logs -f
```

---

## Logging

### Console (default)

Logs go to stderr with levels:

- `INFO` – normal operations
- `WARNING` – recoverable issues
- `ERROR` – failures

### File logging

Set environment variable `CLAWLET_LOG_FILE=/var/log/clawlet.log` (or path). The CLI automatically configures `loguru` to write to that file in addition to console.

Rotate logs with `logrotate`:

```
/var/log/clawlet.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
```

### Structured JSON logs (optional)

Set `LOG_JSON=1` to output logs as JSON lines (easier for ELK/Graylog).

---

## Monitoring

### Health endpoint (if dashboard enabled)

```
GET http://localhost:8000/health
```

Returns:

```json
{
  "status": "healthy",
  "timestamp": "2026-02-24T05:00:00Z",
  "checks": [
    {"name": "provider", "status": "healthy", "message": "..."},
    {"name": "storage", "status": "healthy", "message": "..."},
    {"name": "memory", "status": "healthy", "message": "..."}
  ]
}
```

### Logs to watch

- `provider` errors → OpenRouter API issues
- `storage` errors → DB connection/problems
- `circuit breaker` messages → provider down

---

## Debugging

### Increase log verbosity

Set `LOG_LEVEL=DEBUG` environment variable.

```bash
export LOG_LEVEL=DEBUG
clawlet agent
```

### Dump current memory

Copy contents of `~/.clawlet/MEMORY.md` to see long‑term memories.

### Inspect SQLite database

```bash
sqlite3 ~/.clawlet/clawlet.db
.tables
SELECT * FROM messages LIMIT 10;
SELECT COUNT(*) FROM messages;
```

### Simulate a message

From another terminal:

```bash
curl -X POST http://localhost:8000/agent/message \
  -H "Content-Type: application/json" \
  -d '{"content":"Test"}'
```

(If you expose an API; otherwise use Telegram.)

---

## Configuration Reload

If you edit `config.yaml`, you can reload without restart:

```bash
# Send SIGUSR1 to the process (if running as daemon)
kill -USR1 <pid>
```

Or restart the service:

```bash
sudo systemctl restart clawlet
```

---

## Backups

Important files:

- `~/.clawlet/config.yaml` – API keys, tokens
- `~/.clawlet/clawlet.db` – message history
- `~/.clawlet/MEMORY.md` – long‑term memories

Backup regularly:

```bash
tar czf clawlet-backup-$(date +%F).tar.gz \
  ~/.clawlet/config.yaml \
  ~/.clawlet/clawlet.db \
  ~/.clawlet/MEMORY.md
```

---

## Restoring from Backup

1. Stop the agent: `systemctl stop clawlet` or `Ctrl+C`
2. Restore files to `~/.clawlet/`
3. Ensure correct permissions: `chmod 600 ~/.clawlet/config.yaml`
4. Restart: `systemctl start clawlet`

---

## Updating Clawlet

```bash
cd /path/to/clawlet
git pull
source .venv/bin/activate
pip install -r requirements-core.txt --upgrade
# Optional: run migrations if schema changed
systemctl restart clawlet
```

---

## Metrics (if metrics endpoint enabled)

`GET /metrics` (Prometheus format) – currently only available when dashboard is running.

Metrics include:

- `clawlet_messages_total`
- `clawlet_errors_total`
- `clawlet_uptime_seconds`

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| No response to Telegram messages | Telegram token missing or bot not started | Check `config.yaml`, ensure `channels.telegram.enabled: true` and token set. Restart. |
| "Provider error 401" | Invalid OpenRouter API key | Verify `OPENROUTER_API_KEY` in config or env. |
| Messages not persisted | Storage not initialized or DB permission denied | Check logs for storage errors; ensure `~/.clawlet/` writable. |
| High memory usage | History not trimmed (bug) | Ensure `MAX_HISTORY` is respected; check `agent/loop.py`. |
| Frequent timeouts | LLM provider slow or down | Check provider status; retry/backoff will handle transient failures. |

---

## Security Checklist

- [ ] `config.yaml` permissions: `chmod 600 ~/.clawlet/config.yaml`
- [ ] Use strong, unique API keys
- [ ] Do not expose dashboard port (8000) to public internet (bind to 127.0.0.1 or use firewall)
- [ ] Regularly rotate API keys
- [ ] Keep system packages updated

---

## Support

For bugs and feature requests, visit the repository: https://github.com/your‑org/clawlet
