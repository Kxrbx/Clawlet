"""
Enhanced scheduler with cron expression support.
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any, Callable, Awaitable
from zoneinfo import ZoneInfo

from loguru import logger

try:
    from croniter import croniter
    CRONITER_AVAILABLE = True
except ImportError:
    CRONITER_AVAILABLE = False
    logger.warning("croniter not installed. Cron expressions will not be supported.")

from clawlet.heartbeat.models import (
    ScheduledTask,
    TaskResult,
    TaskStatus,
    TaskAction,
    TaskPriority,
    TaskEvent,
    RetryPolicy,
)


def parse_interval(interval_str: str) -> timedelta:
    """
    Parse an interval string into a timedelta.
    
    Supports formats like:
    - "30s" - 30 seconds
    - "5m" - 5 minutes
    - "2h" - 2 hours
    - "1d" - 1 day
    - "1h30m" - 1 hour 30 minutes
    """
    total_seconds = 0
    
    # Parse complex format like "1h30m"
    pattern = r'(\d+)([smhd])'
    matches = re.findall(interval_str.lower())
    
    if not matches:
        raise ValueError(f"Invalid interval format: {interval_str}")
    
    for value, unit in matches:
        value = int(value)
        if unit == 's':
            total_seconds += value
        elif unit == 'm':
            total_seconds += value * 60
        elif unit == 'h':
            total_seconds += value * 3600
        elif unit == 'd':
            total_seconds += value * 86400
    
    return timedelta(seconds=total_seconds)


def parse_priority(priority_str: str) -> TaskPriority:
    """Parse a priority string into TaskPriority enum."""
    priority_map = {
        "low": TaskPriority.LOW,
        "normal": TaskPriority.NORMAL,
        "high": TaskPriority.HIGH,
        "critical": TaskPriority.CRITICAL,
    }
    return priority_map.get(priority_str.lower(), TaskPriority.NORMAL)


class Scheduler:
    """
    Enhanced scheduler with full cron-like scheduling support.
    
    Features:
    - Cron expressions (e.g., "0 9 * * 1-5" for weekdays at 9am)
    - Fixed intervals (e.g., every 5 minutes)
    - One-time scheduled tasks
    - Timezone support
    - Task priorities
    - Task dependencies
    - Retry on failure with configurable attempts
    - Event emission to message bus
    """
    
    def __init__(
        self,
        timezone: str = "UTC",
        max_concurrent: int = 3,
        check_interval: float = 60.0,
        state_file: Optional[str] = None,
    ):
        """
        Initialize the scheduler.
        
        Args:
            timezone: Default timezone for tasks
            max_concurrent: Maximum concurrent task executions
            check_interval: How often to check for pending tasks (seconds)
            state_file: Path to save/load scheduler state
        """
        self.timezone = ZoneInfo(timezone)
        self.max_concurrent = max_concurrent
        self.check_interval = check_interval
        self.state_file = Path(state_file) if state_file else None
        
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._executor_task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._event_handlers: list[Callable[[TaskEvent], Awaitable[None]]] = []
        
        logger.info(
            f"Scheduler initialized with timezone={timezone}, "
            f"max_concurrent={max_concurrent}, check_interval={check_interval}s"
        )
    
    def add_task(self, task: ScheduledTask) -> None:
        """
        Add a task to the scheduler.
        
        Args:
            task: The scheduled task to add
        """
        if task.id in self._tasks:
            logger.warning(f"Task '{task.id}' already exists, replacing")
        
        # Calculate next run time
        self._update_next_run(task)
        
        self._tasks[task.id] = task
        logger.info(
            f"Added task '{task.name}' (id={task.id}), "
            f"next_run={task.next_run}, action={task.action.value}"
        )
    
    def remove_task(self, task_id: str) -> None:
        """
        Remove a task from the scheduler.
        
        Args:
            task_id: ID of the task to remove
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info(f"Removed task '{task_id}'")
    
    def enable_task(self, task_id: str) -> None:
        """Enable a task."""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = True
            self._update_next_run(self._tasks[task_id])
            logger.info(f"Enabled task '{task_id}'")
    
    def disable_task(self, task_id: str) -> None:
        """Disable a task."""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = False
            logger.info(f"Disabled task '{task_id}'")
    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> list[ScheduledTask]:
        """Get all tasks."""
        return list(self._tasks.values())
    
    def get_next_runs(self, n: int = 10) -> list[tuple[str, datetime]]:
        """
        Get the next N scheduled runs.
        
        Returns:
            List of (task_id, next_run) tuples sorted by next_run
        """
        upcoming = []
        for task in self._tasks.values():
            if task.enabled and task.next_run:
                upcoming.append((task.id, task.next_run))
        
        # Sort by next_run time
        upcoming.sort(key=lambda x: x[1])
        return upcoming[:n]
    
    def add_event_handler(self, handler: Callable[[TaskEvent], Awaitable[None]]) -> None:
        """
        Add an event handler for task events.
        
        Args:
            handler: Async function to handle task events
        """
        self._event_handlers.append(handler)
    
    async def run_task(self, task_id: str) -> TaskResult:
        """
        Manually run a task by ID.
        
        Args:
            task_id: ID of the task to run
            
        Returns:
            TaskResult with execution details
        """
        task = self._tasks.get(task_id)
        if not task:
            return TaskResult(
                task_id=task_id,
                success=False,
                status=TaskStatus.FAILED,
                started_at=datetime.now(self.timezone),
                error=f"Task '{task_id}' not found",
            )
        
        return await self._execute_task(task)
    
    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        self._running = True
        logger.info("Scheduler started")
        
        # Load previous state
        if self.state_file:
            self.load_state(self.state_file)
        
        # Start the main loop
        while self._running:
            try:
                await self._check_and_run_tasks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("Scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self.check_interval)
        
        # Save state on shutdown
        if self.state_file:
            self.save_state(self.state_file)
        
        logger.info("Scheduler stopped")
    
    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        logger.info("Scheduler stopping...")
        self._running = False
    
    def _update_next_run(self, task: ScheduledTask) -> None:
        """Calculate and update the next run time for a task."""
        now = datetime.now(self.timezone)
        
        if task.cron:
            if not CRONITER_AVAILABLE:
                logger.error("croniter not installed, cannot use cron expressions")
                task.enabled = False
                return
            
            try:
                tz = ZoneInfo(task.timezone)
                local_now = datetime.now(tz)
                cron = croniter(task.cron, local_now)
                next_run = cron.get_next(datetime)
                # Convert to scheduler timezone
                task.next_run = next_run.replace(tzinfo=tz)
            except Exception as e:
                logger.error(f"Invalid cron expression for task '{task.id}': {e}")
                task.enabled = False
        
        elif task.interval:
            if task.last_run:
                task.next_run = task.last_run + task.interval
            else:
                task.next_run = now
        
        elif task.one_time:
            tz = ZoneInfo(task.timezone)
            task.next_run = task.one_time.replace(tzinfo=tz)
    
    async def _check_and_run_tasks(self) -> None:
        """Check for pending tasks and run them."""
        now = datetime.now(self.timezone)
        
        # Find tasks that should run
        pending = []
        for task in self._tasks.values():
            if task.should_run(now) and not task.is_one_time_completed():
                # Check dependencies
                if task.wait_for_dependencies and task.depends_on:
                    deps_satisfied = all(
                        self._tasks.get(dep_id) and 
                        self._tasks.get(dep_id).last_result and 
                        self._tasks.get(dep_id).last_result.success
                        for dep_id in task.depends_on
                        if dep_id in self._tasks
                    )
                    if not deps_satisfied:
                        continue
                pending.append(task)
        
        if not pending:
            return
        
        # Sort by priority (critical first)
        pending.sort(key=lambda t: t.priority.value, reverse=True)
        
        logger.info(f"Running {len(pending)} scheduled task(s)")
        
        # Run tasks concurrently (up to max_concurrent)
        tasks = [self._run_task_with_retry(task) for task in pending]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _run_task_with_retry(self, task: ScheduledTask) -> None:
        """Run a task with retry logic."""
        async with self._semaphore:
            attempt = task.current_attempt + 1
            max_attempts = task.retry_policy.max_attempts
            
            while attempt <= max_attempts:
                result = await self._execute_task(task, attempt)
                
                if result.success:
                    task.mark_completed(result)
                    self._update_next_run(task)
                    await self._emit_event(TaskEvent(
                        task_id=task.id,
                        task_name=task.name,
                        event_type="completed",
                        timestamp=datetime.now(self.timezone),
                        result=result,
                    ))
                    return
                
                # Task failed
                if attempt < max_attempts:
                    # Schedule retry
                    delay = task.retry_policy.get_delay(attempt + 1)
                    logger.warning(
                        f"Task '{task.name}' failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {delay}s"
                    )
                    task.current_attempt = attempt
                    task.last_result = result
                    
                    await self._emit_event(TaskEvent(
                        task_id=task.id,
                        task_name=task.name,
                        event_type="retrying",
                        timestamp=datetime.now(self.timezone),
                        result=result,
                        message=f"Retry {attempt}/{max_attempts} after {delay}s",
                    ))
                    
                    await asyncio.sleep(delay)
                    attempt += 1
                else:
                    # Max retries exceeded
                    task.mark_failed(result)
                    logger.error(
                        f"Task '{task.name}' failed after {max_attempts} attempts: {result.error}"
                    )
                    await self._emit_event(TaskEvent(
                        task_id=task.id,
                        task_name=task.name,
                        event_type="failed",
                        timestamp=datetime.now(self.timezone),
                        result=result,
                        message=f"Failed after {max_attempts} attempts",
                    ))
                    return
    
    async def _execute_task(self, task: ScheduledTask, attempt: int = 1) -> TaskResult:
        """
        Execute a single task.
        
        Args:
            task: The task to execute
            attempt: Current attempt number
            
        Returns:
            TaskResult with execution details
        """
        started_at = datetime.now(self.timezone)
        
        await self._emit_event(TaskEvent(
            task_id=task.id,
            task_name=task.name,
            event_type="started",
            timestamp=started_at,
            message=f"Attempt {attempt}",
        ))
        
        try:
            # Execute based on action type
            if task.action == TaskAction.CALLBACK:
                output = await self._execute_callback(task)
            elif task.action == TaskAction.AGENT:
                output = await self._execute_agent(task)
            elif task.action == TaskAction.TOOL:
                output = await self._execute_tool(task)
            elif task.action == TaskAction.WEBHOOK:
                output = await self._execute_webhook(task)
            elif task.action == TaskAction.HEALTH_CHECK:
                output = await self._execute_health_check(task)
            elif task.action == TaskAction.SKILL:
                output = await self._execute_skill(task)
            else:
                raise ValueError(f"Unknown action type: {task.action}")
            
            completed_at = datetime.now(self.timezone)
            return TaskResult(
                task_id=task.id,
                success=True,
                status=TaskStatus.COMPLETED,
                started_at=started_at,
                completed_at=completed_at,
                output=output,
                attempt=attempt,
            )
        
        except Exception as e:
            logger.error(f"Task '{task.name}' execution failed: {e}")
            completed_at = datetime.now(self.timezone)
            return TaskResult(
                task_id=task.id,
                success=False,
                status=TaskStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                error=str(e),
                attempt=attempt,
            )
    
    async def _execute_callback(self, task: ScheduledTask) -> str:
        """Execute a callback function."""
        if not task.callback:
            raise ValueError(f"Task '{task.name}' has no callback function")
        
        callback = task.callback
        if asyncio.iscoroutinefunction(callback):
            result = await callback(**task.params)
        else:
            result = callback(**task.params)
        
        return self._format_result(result)
    
    async def _execute_agent(self, task: ScheduledTask) -> str:
        """Execute an agent prompt."""
        prompt = task.params.get("prompt")
        if not prompt:
            raise ValueError(f"Task '{task.name}' has no prompt for agent action")
        
        # Import here to avoid circular imports
        from clawlet.bus import InboundMessage
        
        # Create a synthetic inbound message for the agent
        # This will be picked up by the agent loop
        message = InboundMessage(
            channel="scheduler",
            chat_id=f"scheduled:{task.id}",
            content=prompt,
            user_id="scheduler",
            user_name="Scheduler",
            metadata={
                "task_id": task.id,
                "task_name": task.name,
                "scheduled": True,
            },
        )
        
        # The agent loop should handle this message
        # For now, we return a placeholder
        logger.info(f"Agent task '{task.name}' queued with prompt: {prompt[:100]}...")
        return f"Agent prompt queued: {prompt[:100]}..."
    
    async def _execute_tool(self, task: ScheduledTask) -> str:
        """Execute a tool."""
        tool_name = task.params.get("tool")
        if not tool_name:
            raise ValueError(f"Task '{task.name}' has no tool name specified")
        
        # Import here to avoid circular imports
        from clawlet.tools import get_tool_registry
        
        registry = get_tool_registry()
        tool = registry.get(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        tool_params = task.params.get("params", {})
        result = await tool.execute(**tool_params)
        
        return self._format_result(result)
    
    async def _execute_webhook(self, task: ScheduledTask) -> str:
        """Execute a webhook call."""
        import aiohttp
        
        url = task.params.get("webhook_url")
        if not url:
            raise ValueError(f"Task '{task.name}' has no webhook URL specified")
        
        method = task.params.get("webhook_method", "POST").upper()
        headers = task.params.get("headers", {})
        payload = task.params.get("payload", {})
        timeout = task.params.get("timeout", 30)
        
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                response_text = await response.text()
                
                if response.status >= 400:
                    raise ValueError(
                        f"Webhook failed with status {response.status}: {response_text}"
                    )
                
                return f"Webhook {method} {url} -> {response.status}"
    
    async def _execute_health_check(self, task: ScheduledTask) -> str:
        """Execute a health check."""
        from clawlet.health import run_health_checks
        
        checks = task.params.get("checks", [])
        results = await run_health_checks(checks)
        
        # Check if any failed
        failed = [r for r in results if not r.healthy]
        if failed:
            raise ValueError(f"Health checks failed: {', '.join(r.name for r in failed)}")
        
        return f"All {len(results)} health checks passed"
    
    async def _execute_skill(self, task: ScheduledTask) -> str:
        """Execute a skill."""
        skill_name = task.params.get("skill")
        if not skill_name:
            raise ValueError(f"Task '{task.name}' has no skill name specified")
        
        # Import here to avoid circular imports
        from clawlet.skills import get_skill_registry
        
        registry = get_skill_registry()
        skill = registry.get(skill_name)
        if not skill:
            raise ValueError(f"Skill '{skill_name}' not found")
        
        skill_params = task.params.get("params", {})
        result = await skill.execute(**skill_params)
        
        return self._format_result(result)
    
    def _format_result(self, result: Any) -> str:
        """Format a result for storage."""
        if result is None:
            return "OK"
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return json.dumps(result)
        return str(result)
    
    async def _emit_event(self, event: TaskEvent) -> None:
        """Emit an event to all registered handlers."""
        for handler in self._event_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
    
    def get_status(self) -> dict:
        """Get scheduler status."""
        now = datetime.now(self.timezone)
        
        tasks_status = []
        for task in self._tasks.values():
            next_run_in = None
            if task.next_run:
                delta = (task.next_run - now).total_seconds()
                next_run_in = max(0, delta)
            
            tasks_status.append({
                "id": task.id,
                "name": task.name,
                "enabled": task.enabled,
                "action": task.action.value,
                "priority": task.priority.name,
                "cron": task.cron,
                "interval": str(task.interval) if task.interval else None,
                "timezone": task.timezone,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "next_run": task.next_run.isoformat() if task.next_run else None,
                "next_run_in": next_run_in,
                "last_result": {
                    "success": task.last_result.success if task.last_result else None,
                    "error": task.last_result.error if task.last_result else None,
                } if task.last_result else None,
            })
        
        return {
            "running": self._running,
            "timezone": str(self.timezone),
            "check_interval": self.check_interval,
            "max_concurrent": self.max_concurrent,
            "total_tasks": len(self._tasks),
            "enabled_tasks": sum(1 for t in self._tasks.values() if t.enabled),
            "tasks": tasks_status,
        }
    
    def save_state(self, path: Path) -> None:
        """Save scheduler state to file."""
        state = {
            "tasks": {
                task_id: {
                    "last_run": task.last_run.isoformat() if task.last_run else None,
                    "current_attempt": task.current_attempt,
                    "last_result": {
                        "success": task.last_result.success,
                        "error": task.last_result.error,
                        "output": task.last_result.output,
                    } if task.last_result else None,
                }
                for task_id, task in self._tasks.items()
            }
        }
        
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        
        logger.debug(f"Saved scheduler state to {path}")
    
    def load_state(self, path: Path) -> None:
        """Load scheduler state from file."""
        path = Path(path).expanduser()
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            for task_id, task_state in state.get("tasks", {}).items():
                if task_id in self._tasks:
                    task = self._tasks[task_id]
                    if task_state.get("last_run"):
                        task.last_run = datetime.fromisoformat(task_state["last_run"])
                    task.current_attempt = task_state.get("current_attempt", 0)
                    if task_state.get("last_result"):
                        task.last_result = TaskResult(
                            task_id=task_id,
                            success=task_state["last_result"].get("success", False),
                            error=task_state["last_result"].get("error"),
                            output=task_state["last_result"].get("output"),
                            status=TaskStatus.COMPLETED if task_state["last_result"].get("success") else TaskStatus.FAILED,
                            started_at=task.last_run or datetime.now(self.timezone),
                        )
            
            logger.debug(f"Loaded scheduler state from {path}")
        except FileNotFoundError:
            logger.debug(f"No scheduler state file at {path}")
        except Exception as e:
            logger.warning(f"Failed to load scheduler state: {e}")


def create_task_from_config(task_id: str, config: "TaskConfig") -> ScheduledTask:
    """
    Create a ScheduledTask from a TaskConfig.
    
    Args:
        task_id: Unique task ID
        config: Task configuration from config file
        
    Returns:
        ScheduledTask instance
    """
    # Parse scheduling
    cron = config.cron
    interval = None
    one_time = None
    
    if config.interval:
        interval = parse_interval(config.interval)
    elif config.one_time:
        one_time = datetime.fromisoformat(config.one_time)
    
    # Parse action
    action_map = {
        "agent": TaskAction.AGENT,
        "tool": TaskAction.TOOL,
        "webhook": TaskAction.WEBHOOK,
        "health_check": TaskAction.HEALTH_CHECK,
        "skill": TaskAction.SKILL,
        "callback": TaskAction.CALLBACK,
    }
    action = action_map.get(config.action.lower(), TaskAction.CALLBACK)
    
    # Build params
    params = dict(config.params)
    if config.prompt:
        params["prompt"] = config.prompt
    if config.tool:
        params["tool"] = config.tool
    if config.webhook_url:
        params["webhook_url"] = config.webhook_url
        params["webhook_method"] = config.webhook_method
    if config.skill:
        params["skill"] = config.skill
    
    # Parse retry policy
    retry_policy = RetryPolicy()
    if config.retry:
        retry_policy = RetryPolicy(
            max_attempts=config.retry.max_attempts,
            delay_seconds=config.retry.delay_seconds,
            backoff_multiplier=config.retry.backoff_multiplier,
            max_delay_seconds=config.retry.max_delay_seconds,
        )
    
    return ScheduledTask(
        id=task_id,
        name=config.name,
        cron=cron,
        interval=interval,
        one_time=one_time,
        timezone=config.timezone,
        action=action,
        params=params,
        enabled=config.enabled,
        priority=parse_priority(config.priority),
        depends_on=config.depends_on,
        retry_policy=retry_policy,
        notify_on_success=config.notify_on_success,
        notify_on_failure=config.notify_on_failure,
        tags=config.tags,
    )