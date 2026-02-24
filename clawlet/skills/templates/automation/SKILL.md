---
name: automation
version: "1.0.0"
description: Automate [TASK_TYPE] tasks with scheduling and monitoring
author: your_name
requires: []
tools:
  - name: create_task
    description: Create a new automated task
    parameters:
      - name: name
        type: string
        description: Task name for identification
        required: true
      - name: action
        type: string
        description: What the task should do
        required: true
      - name: schedule
        type: string
        description: When to run (cron expression or natural language)
        required: true
      - name: enabled
        type: boolean
        description: Whether to enable the task immediately
        required: false
        default: true
  - name: list_tasks
    description: List all automated tasks
    parameters:
      - name: status
        type: string
        description: Filter by status
        required: false
        enum:
          - "all"
          - "enabled"
          - "disabled"
          - "running"
        default: "all"
  - name: run_task
    description: Manually run a task immediately
    parameters:
      - name: task_id
        type: string
        description: ID or name of the task to run
        required: true
  - name: update_task
    description: Update an existing task
    parameters:
      - name: task_id
        type: string
        description: ID or name of the task to update
        required: true
      - name: schedule
        type: string
        description: New schedule (optional)
        required: false
      - name: enabled
        type: boolean
        description: Enable or disable the task
        required: false
  - name: delete_task
    description: Delete an automated task
    parameters:
      - name: task_id
        type: string
        description: ID or name of the task to delete
        required: true
  - name: get_status
    description: Get status of the automation system
    parameters: []
---

# Automation Skill

This skill enables the agent to create, manage, and monitor automated tasks.

## Overview

The automation skill allows you to:
- Create scheduled tasks that run automatically
- Run one-time or recurring actions
- Monitor task execution and status
- Manage existing tasks

## Available Tools

### create_task

Create a new automated task with a schedule.

**Parameters:**
- `name` (required): A descriptive name for the task
- `action` (required): What the task should do
- `schedule` (required): When to run
- `enabled` (optional): Start immediately? (default: true)

### list_tasks

View all configured tasks.

**Parameters:**
- `status` (optional): Filter by status (default: "all")

### run_task

Execute a task immediately, regardless of schedule.

**Parameters:**
- `task_id` (required): Task ID or name

### update_task

Modify an existing task.

**Parameters:**
- `task_id` (required): Task ID or name
- `schedule` (optional): New schedule
- `enabled` (optional): Enable/disable

### delete_task

Remove a task permanently.

**Parameters:**
- `task_id` (required): Task ID or name

### get_status

Check the automation system status.

## Schedule Formats

The `schedule` parameter accepts multiple formats:

### Cron Expressions

Standard 5-field cron syntax:

| Field | Allowed Values |
|-------|---------------|
| Minute | 0-59 |
| Hour | 0-23 |
| Day of Month | 1-31 |
| Month | 1-12 |
| Day of Week | 0-7 (0 and 7 are Sunday) |

**Examples:**
- `0 9 * * *` - Every day at 9:00 AM
- `*/15 * * * *` - Every 15 minutes
- `0 9 * * 1-5` - Weekdays at 9:00 AM
- `0 0 1 * *` - First day of month at midnight

### Natural Language

Human-readable expressions:

- "every 5 minutes"
- "every hour"
- "every day at 9am"
- "every monday at 10am"
- "every weekday at 8:30am"

### Intervals

Simple interval format:

- "5m" - Every 5 minutes
- "1h" - Every hour
- "1d" - Every day

## Usage Examples

### Example 1: Daily Summary

```
User: "Send me a daily summary at 6pm"
Agent: I'll create a daily task for that.
[Calls create_task with name="Daily Summary", action="Generate and send daily summary", schedule="0 18 * * *"]
Agent: Created! You'll receive a daily summary at 6 PM.
```

### Example 2: Periodic Check

```
User: "Check the API status every 5 minutes"
Agent: I'll set up a periodic check.
[Calls create_task with name="API Status Check", action="Check API health endpoint", schedule="every 5 minutes"]
Agent: Done! The API will be checked every 5 minutes.
```

### Example 3: Weekly Report

```
User: "Generate a report every Monday at 9am"
Agent: I'll create a weekly report task.
[Calls create_task with name="Weekly Report", action="Generate weekly report", schedule="0 9 * * 1"]
Agent: Created! Reports will be generated every Monday at 9 AM.
```

### Example 4: Run Immediately

```
User: "Run the daily summary task now"
Agent: I'll run that task immediately.
[Calls run_task with task_id="Daily Summary"]
Agent: Task completed! [Shows results]
```

### Example 5: Disable a Task

```
User: "Pause the API check for now"
Agent: I'll disable that task.
[Calls update_task with task_id="API Status Check", enabled=false]
Agent: The API check is now paused. Say "resume" when you want to enable it again.
```

## Task Actions

The `action` parameter describes what the task should do. The agent interprets this and executes accordingly.

**Common Actions:**
- "Send email to X with Y"
- "Check Z and notify if condition"
- "Generate report about X"
- "Clean up files older than Y"
- "Fetch data from X and process"

## Best Practices

1. **Clear Names**: Use descriptive task names for easy identification
2. **Appropriate Scheduling**: Don't overload with too frequent tasks
3. **Error Handling**: Tasks should handle errors gracefully
4. **Notifications**: Consider how to notify on task completion/failure
5. **Testing**: Run tasks manually first to verify behavior

## Limitations

- Tasks require the agent to be running
- Maximum concurrent tasks may be limited
- Long-running tasks may timeout
- Task history retention may be limited

## Monitoring

Use `get_status` to check:
- Number of active tasks
- Recent execution history
- System health
- Error counts

## Security Notes

- Validate task actions before execution
- Be cautious with file system operations
- Limit access to sensitive operations
- Log task executions for auditing