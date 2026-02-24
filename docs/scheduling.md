# Scheduling Documentation

Clawlet's scheduling system enables autonomous task execution at specified times or intervals. This is useful for periodic tasks like daily summaries, health checks, and automated workflows.

## Table of Contents

- [Overview](#overview)
- [Cron Expressions](#cron-expressions)
- [Interval Tasks](#interval-tasks)
- [Task Actions](#task-actions)
- [Configuration Examples](#configuration-examples)
- [HEARTBEAT.md Format](#heartbeatsmd-format)
- [Advanced Features](#advanced-features)

---

## Overview

The scheduling system provides:

- **Cron Expressions** - Full cron syntax for precise scheduling
- **Fixed Intervals** - Simple interval-based execution
- **One-Time Tasks** - Execute once at a specific time
- **Timezone Support** - Schedule in any timezone
- **Retry Logic** - Automatic retry on failure
- **Task Priorities** - Control execution order

### Components

| Component | Purpose |
|-----------|---------|
| `Scheduler` | Main scheduler with cron support |
| `ScheduledTask` | Task definition with scheduling info |
| `TaskAction` | Types of actions tasks can perform |
| `RetryPolicy` | Configure retry behavior |

---

## Cron Expressions

Cron expressions provide precise control over when tasks run.

### Syntax

Standard 5-field cron format:

```
# Format
minute hour day-of-month month day-of-week

# Example: Every day at 9:00 AM
0 9 * * *
```

### Field Values

| Field | Allowed Values | Special Characters |
|-------|---------------|-------------------|
| Minute | 0-59 | `*` `,` `-` `/` |
| Hour | 0-23 | `*` `,` `-` `/` |
| Day of Month | 1-31 | `*` `,` `-` `/` |
| Month | 1-12 | `*` `,` `-` `/` |
| Day of Week | 0-7 (0,7 = Sunday) | `*` `,` `-` `/` |

### Special Characters

| Character | Meaning | Example |
|-----------|---------|---------|
| `*` | Any value | `* * * * *` = every minute |
| `,` | Value list | `0,30 * * * *` = every 30 minutes |
| `-` | Range | `0 9-17 * * *` = hourly 9am-5pm |
| `/` | Step | `*/15 * * * *` = every 15 minutes |

### Common Examples

| Expression | Description |
|------------|-------------|
| `0 9 * * *` | Every day at 9:00 AM |
| `0 9 * * 1-5` | Weekdays at 9:00 AM |
| `*/15 * * * *` | Every 15 minutes |
| `0 */2 * * *` | Every 2 hours |
| `0 0 * * 0` | Every Sunday at midnight |
| `0 0 1 * *` | First day of month at midnight |
| `0 9 1 1 *` | January 1st at 9:00 AM |
| `0 9,12,18 * * *` | 9am, noon, and 6pm daily |

### Timezone Support

Cron expressions are evaluated in the configured timezone:

```yaml
scheduler:
  timezone: "America/New_York"
```

---

## Interval Tasks

For simpler scheduling, use interval-based tasks.

### Interval Format

| Format | Description |
|--------|-------------|
| `30s` | Every 30 seconds |
| `5m` | Every 5 minutes |
| `1h` | Every hour |
| `1d` | Every day |
| `1h30m` | Every 1 hour 30 minutes |

### Configuration

```yaml
tasks:
  - name: health_check
    interval: "5m"
    action: health_check
```

### Interval vs Cron

| Feature | Interval | Cron |
|---------|----------|------|
| Simplicity | Simple | Complex |
| Precision | Relative | Absolute |
| Time-of-day | No | Yes |
| Timezone | Not applicable | Supported |

Use **interval** for relative timing (every X minutes).
Use **cron** for absolute timing (every day at 9am).

---

## Task Actions

Tasks can perform various actions:

### Available Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `agent` | Send a prompt to the agent | `prompt` |
| `tool` | Execute a specific tool | `tool_name`, `params` |
| `webhook` | Call an external webhook | `url`, `method`, `data` |
| `health_check` | Run health checks | `checks` |
| `skill` | Execute a skill | `skill_name`, `tool`, `params` |
| `callback` | Run a Python function | `function` |

### Agent Action

Send a prompt to the agent for processing:

```yaml
tasks:
  - name: daily_summary
    cron: "0 18 * * *"
    action: agent
    prompt: "Generate a summary of today's activity and send it to the user"
```

### Tool Action

Execute a specific tool directly:

```yaml
tasks:
  - name: cleanup_files
    interval: "1d"
    action: tool
    tool_name: "file_delete"
    params:
      path: "/tmp/old_files"
      pattern: "*.tmp"
```

### Webhook Action

Call an external webhook:

```yaml
tasks:
  - name: notify_status
    cron: "0 9 * * *"
    action: webhook
    url: "https://api.example.com/status"
    method: "POST"
    data:
      status: "active"
      timestamp: "{{now}}"
```

### Health Check Action

Run system health checks:

```yaml
tasks:
  - name: periodic_health
    interval: "5m"
    action: health_check
    checks:
      - provider
      - storage
      - channels
```

### Skill Action

Execute a skill tool:

```yaml
tasks:
  - name: send_reminder
    cron: "0 9 * * *"
    action: skill
    skill_name: "email"
    tool: "send_email"
    params:
      to: "user@example.com"
      subject: "Daily Reminder"
      body: "Don't forget your tasks today!"
```

---

## Configuration Examples

### Daily Summary

Send a daily summary at 6 PM:

```yaml
scheduler:
  enabled: true
  timezone: "America/New_York"
  tasks:
    - name: daily_summary
      cron: "0 18 * * *"
      action: agent
      prompt: |
        Generate a summary of today's activity:
        1. Messages received
        2. Tasks completed
        3. Any issues encountered
        Send this summary to the user via their preferred channel.
```

### Periodic Health Checks

Check system health every 5 minutes:

```yaml
scheduler:
  tasks:
    - name: health_monitor
      interval: "5m"
      action: health_check
      checks:
        - provider
        - storage
      on_failure:
        notify: true
        channel: telegram
```

### Weekly Report

Generate a report every Monday at 9 AM:

```yaml
scheduler:
  tasks:
    - name: weekly_report
      cron: "0 9 * * 1"
      action: agent
      prompt: "Generate a weekly report summarizing all activity from the past 7 days"
```

### Multiple Daily Tasks

Run tasks at multiple times:

```yaml
scheduler:
  tasks:
    - name: morning_brief
      cron: "0 8 * * *"
      action: agent
      prompt: "Good morning! Provide a brief of today's schedule."
    
    - name: lunch_reminder
      cron: "0 12 * * *"
      action: agent
      prompt: "Remind the user it's lunch time."
    
    - name: evening_wrap
      cron: "0 18 * * *"
      action: agent
      prompt: "Summarize today's completed tasks."
```

---

## HEARTBEAT.md Format

Tasks can be defined in `HEARTBEAT.md` for workspace-level configuration.

### Basic Format

```markdown
# Heartbeat Tasks

## Daily Summary
- Schedule: 0 18 * * *
- Action: Generate daily summary
- Timezone: America/New_York

## Health Check
- Interval: 5m
- Action: Run health checks
```

### YAML Block Format

```markdown
# Heartbeat Tasks

```yaml
tasks:
  - name: daily_summary
    cron: "0 18 * * *"
    action: agent
    prompt: "Generate daily summary"
  
  - name: health_check
    interval: "5m"
    action: health_check
```
```

---

## Advanced Features

### Task Priorities

Control execution order when multiple tasks are due:

```yaml
tasks:
  - name: critical_alert
    priority: critical
    cron: "*/5 * * * *"
    action: agent
    prompt: "Check for critical alerts"
  
  - name: daily_summary
    priority: normal
    cron: "0 18 * * *"
    action: agent
    prompt: "Generate summary"
```

Priority levels:
- `critical` - Execute immediately
- `high` - High priority queue
- `normal` - Standard priority (default)
- `low` - Background tasks

### Retry Policy

Configure automatic retry on failure:

```yaml
tasks:
  - name: api_sync
    interval: "1h"
    action: webhook
    url: "https://api.example.com/sync"
    retry:
      max_attempts: 3
      delay_seconds: 60
      backoff_multiplier: 2.0
      max_delay_seconds: 3600
```

Retry behavior:
1. First failure: Wait 60 seconds, retry
2. Second failure: Wait 120 seconds, retry
3. Third failure: Wait 240 seconds, retry
4. Fourth failure: Give up (max attempts reached)

### Task Dependencies

Run tasks after other tasks complete:

```yaml
tasks:
  - name: fetch_data
    cron: "0 6 * * *"
    action: webhook
    url: "https://api.example.com/data"
  
  - name: process_data
    depends_on: fetch_data
    action: agent
    prompt: "Process the fetched data and generate insights"
```

### One-Time Tasks

Execute once at a specific time:

```yaml
tasks:
  - name: reminder
    one_time: "2024-12-25T09:00:00"
    timezone: "America/New_York"
    action: agent
    prompt: "Remind the user about the holiday event"
```

### Task Metadata

Add metadata for tracking and logging:

```yaml
tasks:
  - name: daily_backup
    cron: "0 2 * * *"
    action: tool
    tool_name: "file_backup"
    metadata:
      owner: "admin"
      category: "maintenance"
      notify_on_success: true
```

### Conditional Execution

Run tasks based on conditions:

```yaml
tasks:
  - name: alert_if_issues
    interval: "30m"
    action: agent
    prompt: "Check for any issues and alert if found"
    condition:
      type: "has_issues"  # Custom condition
```

---

## Configuration Reference

### Scheduler Configuration

```yaml
scheduler:
  enabled: true
  timezone: "UTC"
  max_concurrent: 3
  check_interval: 60
  state_file: "~/.clawlet/scheduler_state.json"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable scheduler |
| `timezone` | string | "UTC" | Default timezone |
| `max_concurrent` | int | 3 | Max concurrent tasks |
| `check_interval` | int | 60 | Check interval (seconds) |
| `state_file` | string | null | State persistence file |

### Task Configuration

```yaml
tasks:
  - name: string           # Required: Task name
    id: string             # Optional: Unique ID (auto-generated)
    cron: string           # One of: cron, interval, one_time
    interval: string       # Interval format (e.g., "5m")
    one_time: string       # ISO 8601 datetime
    timezone: string       # Task-specific timezone
    action: string         # Required: Action type
    priority: string       # low, normal, high, critical
    enabled: bool          # Default: true
    depends_on: string     # Task ID to depend on
    retry:                 # Retry policy
      max_attempts: int
      delay_seconds: float
      backoff_multiplier: float
      max_delay_seconds: float
    metadata: dict         # Custom metadata
```

---

## Troubleshooting

### Task Not Running

1. Check scheduler is enabled: `scheduler.enabled: true`
2. Verify cron/interval syntax
3. Check timezone configuration
4. Review logs for errors

### Wrong Execution Time

1. Verify timezone setting
2. Check cron expression
3. Ensure system time is correct

### Task Failures

1. Check retry configuration
2. Review task action parameters
3. Verify external resources (URLs, APIs)
4. Check logs for error details

### Debug Mode

Enable debug logging:

```yaml
logging:
  scheduler: DEBUG
```

---

## See Also

- [Skills Documentation](skills.md) - Create skills for scheduled tasks
- [Webhooks Documentation](webhooks.md) - Trigger webhooks from tasks
- [Multi-Agent Documentation](multi-agent.md) - Route tasks to different agents