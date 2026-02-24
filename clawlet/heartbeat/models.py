"""
Models for the enhanced scheduling system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Any, Callable, Awaitable
import uuid


class TaskPriority(Enum):
    """Priority levels for scheduled tasks."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TaskAction(Enum):
    """Types of actions a scheduled task can perform."""
    AGENT = "agent"           # Send a prompt to the agent
    TOOL = "tool"             # Execute a specific tool
    WEBHOOK = "webhook"       # Call an external webhook
    HEALTH_CHECK = "health_check"  # Run health checks
    SKILL = "skill"           # Execute a skill
    CALLBACK = "callback"     # Execute a Python callback function


class TaskStatus(Enum):
    """Status of a scheduled task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"
    RETRYING = "retrying"


@dataclass
class RetryPolicy:
    """Configuration for retry behavior on task failure."""
    max_attempts: int = 3
    delay_seconds: float = 60.0  # Delay between retries
    backoff_multiplier: float = 2.0  # Exponential backoff multiplier
    max_delay_seconds: float = 3600.0  # Maximum delay between retries (1 hour)
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number (1-indexed)."""
        if attempt <= 1:
            return 0
        delay = self.delay_seconds * (self.backoff_multiplier ** (attempt - 2))
        return min(delay, self.max_delay_seconds)


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    success: bool
    status: TaskStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    output: Optional[str] = None
    error: Optional[str] = None
    attempt: int = 1
    metadata: dict = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get the duration of task execution."""
        if self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class ScheduledTask:
    """
    A scheduled task with full cron-like scheduling support.
    
    Supports:
    - Cron expressions (e.g., "0 9 * * 1-5" for weekdays at 9am)
    - Fixed intervals (e.g., every 5 minutes)
    - One-time execution
    - Timezone-aware scheduling
    - Task dependencies
    - Retry on failure
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    
    # Scheduling options (use one of these)
    cron: Optional[str] = None  # Cron expression (e.g., "0 8 * * *")
    interval: Optional[timedelta] = None  # Fixed interval (e.g., every 5 minutes)
    one_time: Optional[datetime] = None  # One-time execution at specific time
    
    # Timezone for cron/one-time scheduling
    timezone: str = "UTC"
    
    # Action configuration
    action: TaskAction = TaskAction.CALLBACK
    params: dict = field(default_factory=dict)
    
    # For CALLBACK action
    callback: Optional[Callable[[], Awaitable[Any]]] = None
    
    # Task configuration
    enabled: bool = True
    priority: TaskPriority = TaskPriority.NORMAL
    
    # Execution tracking
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    last_result: Optional[TaskResult] = None
    
    # Retry configuration
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    current_attempt: int = 0
    
    # Dependencies
    depends_on: list[str] = field(default_factory=list)  # Task IDs this task depends on
    wait_for_dependencies: bool = True  # Wait for dependencies to complete before running
    
    # Notification settings
    notify_on_success: bool = False
    notify_on_failure: bool = True
    
    # Metadata
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate task configuration."""
        if not self.name:
            self.name = self.id
        
        # Ensure only one scheduling method is specified
        scheduling_methods = sum([
            self.cron is not None,
            self.interval is not None,
            self.one_time is not None,
        ])
        
        if scheduling_methods == 0:
            # Default to daily if no scheduling specified
            self.cron = "0 0 * * *"
        elif scheduling_methods > 1:
            raise ValueError(
                f"Task '{self.name}' has multiple scheduling methods. "
                "Specify only one of: cron, interval, or one_time"
            )
    
    def is_one_time_completed(self) -> bool:
        """Check if a one-time task has already run."""
        return self.one_time is not None and self.last_run is not None
    
    def should_run(self, now: datetime) -> bool:
        """Check if this task should run based on its schedule."""
        if not self.enabled:
            return False
        
        # One-time tasks only run once
        if self.one_time is not None:
            if self.last_run is not None:
                return False
            return now >= self.one_time
        
        # For cron and interval, check next_run
        if self.next_run is None:
            return True  # Never run before
        
        return now >= self.next_run
    
    def mark_completed(self, result: TaskResult) -> None:
        """Mark the task as completed with a result."""
        self.last_run = result.started_at
        self.last_result = result
        self.current_attempt = 0
        
        # For one-time tasks, they're done after completion
        if self.one_time is not None:
            self.enabled = False
    
    def mark_failed(self, result: TaskResult) -> None:
        """Mark the task as failed, potentially for retry."""
        self.last_result = result
        self.current_attempt = result.attempt


@dataclass
class TaskEvent:
    """Event emitted when a task lifecycle event occurs."""
    task_id: str
    task_name: str
    event_type: str  # "started", "completed", "failed", "retrying", "skipped"
    timestamp: datetime
    result: Optional[TaskResult] = None
    message: Optional[str] = None
    metadata: dict = field(default_factory=dict)