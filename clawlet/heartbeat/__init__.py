"""
Heartbeat system for periodic autonomous tasks.

This module provides two schedulers:
1. HeartbeatScheduler - Simple interval-based scheduler (legacy)
2. Scheduler - Enhanced scheduler with cron expressions, timezones, and more
"""

from clawlet.heartbeat.scheduler import (
    HeartbeatScheduler,
    HeartbeatTask,
    HeartbeatPriority,
)

from clawlet.heartbeat.models import (
    ScheduledTask,
    TaskResult,
    TaskStatus,
    TaskAction,
    TaskPriority,
    TaskEvent,
    RetryPolicy,
)

from clawlet.heartbeat.cron_scheduler import (
    Scheduler,
    parse_interval,
    parse_priority,
    create_task_from_config,
)

__all__ = [
    # Legacy heartbeat scheduler
    "HeartbeatScheduler",
    "HeartbeatTask",
    "HeartbeatPriority",
    # Enhanced scheduler
    "Scheduler",
    "ScheduledTask",
    "TaskResult",
    "TaskStatus",
    "TaskAction",
    "TaskPriority",
    "TaskEvent",
    "RetryPolicy",
    # Utility functions
    "parse_interval",
    "parse_priority",
    "create_task_from_config",
]
