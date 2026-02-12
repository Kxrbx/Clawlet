# Deployment Guide — Clawlet

_Last updated: 2026-02-12_

This document provides the single source of truth for running Clawlet components, port assignments, and troubleshooting common issues.

---

## Overview

Clawlet consists of two main components:

| Component | Purpose | Port | Command | Status |
|-----------|---------|------|---------|--------|
| **Website** (Next.js) | Public marketing/docs landing page | `2000` (production)<br>`3000` (dev) | `npm start` (prod)<br>`npm run dev` (dev) | ✅ Running |
| **Dashboard** (React + Vite) | Agent management UI | `5173` (dev only) | `npm run dev` | ✅ Running |
| **Gateway** | OpenClaw daemon | N/A (service) | `openclaw gateway start` | ✅ Running |

**Note:** The production stable port is **2000**. All external access should use port 2000.

---

## Quick Start

### Start All Services (Production)

```bash
# 1. Start OpenClaw Gateway (if not running)
openclaw gateway start

# 2. Start Website in production mode
cd /root/.openclaw/workspace/website
npm start

# Website will be available at http://72.62.239.209:2000
# Dashboard remains at http://localhost:5173/ (development mode)
```

### Start All Services (Development)

```bash
# Gateway (already running in background)
openclaw gateway status

# Website dev server (port 3000)
cd /root/.openclaw/workspace/website
npm run dev

# Dashboard dev server (port 5173)
cd /root/.openclaw/workspace/dashboard
npm run dev
```

---

## Port Assignments

| Port | Service | Access | Purpose |
|------|---------|--------|---------|
| `2000` | Website (production) | External (public IP) | Primary external access point |
| `3000` | Website (development) | Localhost only | Hot-reload development |
| `5173` | Dashboard (development) | Localhost only | Agent management UI |
| `8080` | (former test) | Unused | — |

**Important:** Do not use port 3000 for external access. Always use port 2000 for production.

---

## External Access URLs

### Production (Public)
- **Website:** `http://72.62.239.209:2000`
  - `/` — Landing page
  - `/docs` — Documentation
  - `/dashboard` (if reverse-proxied) — Management UI
  
- **API (FastAPI backend):** Included in website on port 2000
  - `/api/health` — Health check
  - `/api/agents` — Agent list
  - `/api/stats` — System stats

### Local Development
- **Website dev:** `http://localhost:3000`
- **Dashboard dev:** `http://localhost:5173/`
- **OpenClaw Gateway:** No direct URL; controlled via CLI

### Tailscale (VPN)
Attempted: `http://100.111.162.48:2000`  
**Status:** ❌ Not accessible (firewall or routing issue). Use public IP instead.

---

## Commands Reference

### OpenClaw Gateway
```bash
openclaw gateway status     # Check if running
openclaw gateway start      # Start daemon
openclaw gateway stop       # Stop daemon
openclaw gateway restart    # Restart after config changes
openclaw gateway logs       # View logs (if available)
```

### Website (Next.js)
```bash
cd /root/.openclaw/workspace/website

# Production (stable, no hot reload)
npm start                   # Runs on port 2000
npm run build               # Build static files (if needed)

# Development (hot reload)
npm run dev                 # Runs on port 3000
npm run build:dev           # Dev build
```

### Dashboard (React + Vite)
```bash
cd /root/.openclaw/workspace/dashboard

# Development only (no production build configured yet)
npm run dev                 # Runs on port 5173
npm run build               # Future: production build?
npm run preview             # Future: preview build?
```

### Skill Management
```bash
# List installed skills
clawhub list

# Search for new skills
clawhub search "<query>"

# Install skill
clawhub install <slug>

# Update all skills
clawhub update --all

# Inspect skill details
clawhub inspect <slug>

# Update OpenClaw itself
openclaw update
```

---

## Health Checks

### Verify Services

```bash
# 1. Gateway
openclaw gateway status
# Should show: running

# 2. Website (port 2000)
curl -s http://localhost:2000/api/health || echo "❌ Website not responding"
# Should return JSON: {"status":"ok"}

# 3. Dashboard (port 5173)
curl -s http://localhost:5173/ | head -5
# Should return HTML dashboard
```

### System Resources
```bash
# Check memory usage
free -h

# Check CPU load
top -b -n1 | head -10

# Check disk space
df -h

# OpenClaw-specific
openclaw status
```

---

## Troubleshooting

### "Website not accessible" (public URL)

**Symptoms:** `curl http://72.62.239.209:2000` hangs or connection refused.

**Diagnosis:**
```bash
# 1. Is process running?
ps aux | grep "node.*website" | grep -v grep

# 2. Is port listening?
ss -tlnp | grep :2000

# 3. Is firewall blocking?
sudo ufw status  # or iptables -L

# 4. Try localhost (bypass firewall)
curl http://localhost:2000
```

**Fixes:**
- If process not running: `cd website && npm start`
- If port not listening: check logs in `website/.next/standalone` or console output
- If firewall: `sudo ufw allow 2000/tcp`

---

### "Port already in use"

**Symptoms:** `EADDRINUSE` error on startup.

**Diagnosis:**
```bash
# Find process using port
sudo lsof -i :2000
# or
ss -tlnp | grep :2000
```

**Fix:** Kill the conflicting process or change port in `package.json` scripts.

---

### "Tailscale not accessible"

**Symptoms:** `http://100.111.162.48:2000` unreachable from another machine.

**Causes:**
- Tailscale not running on host
- Firewall blocking Tailscale interface
- Port not exposed to Tailscale network

**Fix:**
```bash
# 1. Check Tailscale status
tailscale status

# 2. Check firewall rules for tailscale0
sudo ufw status tailscale0

# 3. Test from host itself
curl http://localhost:2000
# If works locally but not via Tailscale, likely firewall issue
```

**Recommendation:** Use public IP `72.62.239.209:2000` instead. Tailscale access may not be necessary.

---

### "Dashboard not loading"

**Symptoms:** `http://localhost:5173/` shows blank or error.

**Diagnosis:**
```bash
# 1. Is Vite dev server running?
ps aux | grep vite | grep -v grep

# 2. Check console output for errors
# (run in dashboard directory)
npm run dev

# 3. Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
npm run dev
```

---

### "Gateway not starting"

**Symptoms:** `openclaw gateway status` shows stopped.

**Diagnosis:**
```bash
# Check logs
openclaw gateway logs  # if available
# or journalctl
sudo journalctl -u openclaw -n 50

# Common issues:
# - Config syntax error in config.yaml
# - Missing OPENROUTER_API_KEY
# - Port conflict (default 8080?)

# Restart with debug
openclaw gateway restart
```

**Fix:** Resolve config errors (check `/etc/openclaw/config.yaml` or `~/.config/openclaw/`).

---

### "Skill not working"

**Symptoms:** Skill installed but commands fail or not recognized.

**Checklist:**
1. Is skill listed in `clawhub list`?
2. Does skill directory have `SKILL.md`?
3. Are required dependencies installed? (Read SKILL.md)
4. Is configuration present? (e.g., API keys in env vars)
5. Check skill logs: Some skills write to `~/.config/<skill>/` or `skills/<skill>/logs/`

**Example:** `multi-channel-engagement-agent` requires `config.json` with platform credentials.

---

### "Moltbook suspended"

**Symptoms:** Moltbook API returns 403 or "duplicate comments" error.

**Status:** This is expected until ~2026-02-18. Suspension is automatic expiry.

**Workaround:**
- Continue Molthub engagement using `multi-channel-engagement-agent`.
- Study `moltbook-authentic-engagement` protocols for quality-first approach.
- Do NOT attempt to circumvent suspension; repeated offenses may extend it.

**Post-suspension:**
1. Use `moltbook-authentic-engagement` skill (quality gates).
2. Use `moltbook-post-verified` for simple posts.
3. Enable `moltbook-post-verified` hook if available.
4. Monitor rate limits and duplicates carefully.

---

### "Rate limit exceeded" (multi-channel engagement)

**Symptoms:** API 429 errors from Twitter/Farcaster/Moltbook.

**Causes:**
- Qwen 3 4B rate limit (8 RPM) for sub-agents
- Platform-specific rate limits (Twitter: 50 tweets/15min, Farcaster: Neynar 300/min, Moltbook: captcha throttling)

**Mitigation:**
- **Multi-channel agent:** Already has duplicate prevention; respects platform limits.
- **Sub-agent fallback:** If Qwen 3 4B hits limit, script falls back to direct posting with main model (user-reported).
- **Adjust frequency:** In `config.json`, reduce `ms_between_actions` or run less frequently.

---

### "Cannot connect to Tailscale" (from user device)

**Symptoms:** User's machine cannot access `100.111.162.48:2000`.

**Diagnosis:**
```bash
# On user's machine
ping 100.111.162.48
tailscale status
```

**Fix:** Ensure Tailscale is running on both host and client, and both are on same Tailscale network.

**Alternative:** Use public IP `72.62.239.209:2000` (ensure port 2000 open in firewall).

---

## Maintenance Tasks

### Daily
- Check `openclaw gateway status`
- Review website logs for errors
- Verify Molthub engagement is running (check `molthub-post-track.md`)

### Weekly
- `clawhub update --all` — update skills to latest versions
- `clawvault doctor` — check memory vault health
- `node skills/evolver/index.js --review` — review self-improvement suggestions
- `openclaw backup` or `openclaw-update` with backup-only flag

### Monthly
- Review firewall rules (`sudo ufw status`)
- Check disk space (`df -h`)
- Audit installed skills (`clawhub list`) — remove unused ones

---

## Configuration Files

| File | Purpose | Managed By |
|------|---------|------------|
| `/root/.openclaw/workspace/website/.env` | Website env vars | User |
| `/root/.openclaw/workspace/dashboard/.env` | Dashboard env vars | User |
| `/root/.openclaw/workspace/.clawlet/config.yaml` | Clawlet config | Clawlet CLI |
| `/root/.config/clawvault/` | ClawVault storage | clawvault |
| `skills/multi-channel-engagement-agent/config.json` | Engagement platforms | User |
| `~/.config/moltbook-authentic-engagement/config.yaml` | Moltbook authentic config | User |

---

## Environment Variables

| Variable | Purpose | Where set |
|----------|---------|-----------|
| `OPENROUTER_API_KEY` | OpenRouter API access | Gateway config |
| `BRAVE_API_KEY` | Web search | `~/.bashrc` (exported) |
| `MOLTBOOK_API_KEY` | Moltbook posts | `~/.config/...` or env |
| `GEMINI_API_KEY` | ClawVault observe compression | Optional |
| `CLAWVAULT_PATH` | Vault location | Optional |

---

## Monitoring & Alerts

### Heartbeat Checks
During `HEARTBEAT.md` execution, verify:
- Gateway is running
- Website responds on port 2000
- Recent Molthub engagement activity
- ClawVault recent checkpoints

### Cron Jobs (suggested)
```bash
# Every 6 hours: update skills
0 */6 * * * clawhub update --all --no-input

# Daily at 2 AM: backup
0 2 * * * node skills/openclaw-update/index.js --backup-only

# Every 30 min: health check (if not using heartbeat)
*/30 * * * * curl -s http://localhost:2000/api/health || echo "Website down" >> ~/health-alerts.log
```

---

## Security Notes

- API keys stored in environment variables or config files with restricted permissions (`chmod 600`).
- Never commit API keys to git. `.gitignore` should include `.env` and config files with secrets.
- Public server (72.62.239.209): Ensure firewall only allows necessary ports (2000, SSH).
- Production website runs as non-root user (typically).

---

## Support & Resources

- OpenClaw docs: `/root/.nvm/versions/node/v22.22.0/lib/node_modules/openclaw/docs`
- Online: https://docs.openclaw.ai
- Community: https://discord.com/invite/clawd
- Skill-specific: See individual `SKILL.md` files in `skills/`

---

## Quick Command Reference Card

```bash
# Gateway
openclaw gateway {status,start,stop,restart}

# Website (prod)
cd website && npm start

# Website (dev)
cd website && npm run dev

# Dashboard
cd dashboard && npm run dev

# Skills
clawhub {list,search,install,inspect,update}

# Memory
clawvault {wake,sleep,checkpoint,remember,search}

# Engagement
node skills/multi-channel-engagement-agent/scripts/engage.mjs --all

# Maintenance
node skills/evolver/index.js --review
node skills/openclaw-update/index.js

# Health
curl http://localhost:2000/api/health
openclaw status
```

---

**Remember:** Port 2000 is the canonical production port. When in doubt, consult this document first.
