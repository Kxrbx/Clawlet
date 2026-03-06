"""
Enhanced scheduler with cron expression support.
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
import uuid
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
from clawlet.runtime.events import (
    SCHED_PAYLOAD_JOB_ID,
    SCHED_PAYLOAD_RUN_ID,
    SCHED_PAYLOAD_SESSION_TARGET,
    SCHED_PAYLOAD_SOURCE,
    SCHED_PAYLOAD_WAKE_MODE,
)
from clawlet.metrics import get_metrics


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
    matches = re.findall(pattern, interval_str.lower())
    
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
        jobs_file: Optional[str] = None,
        runs_dir: Optional[str] = None,
        message_bus: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        skill_registry: Optional[Any] = None,
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
        self.jobs_file = Path(jobs_file).expanduser() if jobs_file else None
        self.runs_dir = Path(runs_dir).expanduser() if runs_dir else None
        
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._executor_task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._event_handlers: list[Callable[[TaskEvent], Awaitable[None]]] = []
        self._message_bus = message_bus
        self._tool_registry = tool_registry
        self._skill_registry = skill_registry
        self._pending_heartbeat_jobs: list[Any] = []
        
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
        self._persist_jobs_if_configured()
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
            self._persist_jobs_if_configured()
            logger.info(f"Removed task '{task_id}'")
    
    def enable_task(self, task_id: str) -> None:
        """Enable a task."""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = True
            self._update_next_run(self._tasks[task_id])
            self._persist_jobs_if_configured()
            logger.info(f"Enabled task '{task_id}'")
    
    def disable_task(self, task_id: str) -> None:
        """Disable a task."""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = False
            self._persist_jobs_if_configured()
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

        result = await self._execute_task(task)
        if result.success:
            task.mark_completed(result)
            self._update_next_run(task)
            if bool(task.params.get("delete_after_run", False)):
                self.remove_task(task.id)
        else:
            task.mark_failed(result)
        self._record_run(task, result, trigger="manual")
        self._persist_state_if_configured()
        return result
    
    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        self._running = True
        logger.info("Scheduler started")
        
        # Load previous state
        if self.jobs_file:
            self.load_jobs(self.jobs_file, replace=False)
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
        if self.jobs_file:
            self.save_jobs(self.jobs_file)
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
                    deps_satisfied = True
                    for dep_id in task.depends_on:
                        dep_task = self._tasks.get(dep_id)
                        if dep_task is None:
                            deps_satisfied = False
                            break
                        dep_result = dep_task.last_result
                        if dep_result is None or not dep_result.success:
                            deps_satisfied = False
                            break
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
                    self._record_run(task, result, trigger="scheduled")
                    self._persist_state_if_configured()
                    if bool(task.params.get("delete_after_run", False)):
                        self.remove_task(task.id)
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
                    self._record_run(task, result, trigger="scheduled")
                    self._persist_state_if_configured()
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
                    await self._maybe_send_failure_alert(task, result)
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
        get_metrics().inc_scheduled_runs_attempted()
        
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
            result = TaskResult(
                task_id=task.id,
                success=True,
                status=TaskStatus.COMPLETED,
                started_at=started_at,
                completed_at=completed_at,
                output=output,
                attempt=attempt,
            )
            await self._deliver_task_result(task, result)
            get_metrics().inc_scheduled_runs_succeeded()
            return result
        
        except Exception as e:
            logger.error(f"Task '{task.name}' execution failed: {e}")
            completed_at = datetime.now(self.timezone)
            result = TaskResult(
                task_id=task.id,
                success=False,
                status=TaskStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                error=str(e),
                attempt=attempt,
            )
            await self._deliver_task_result(task, result)
            get_metrics().inc_scheduled_runs_failed()
            return result
    
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
        from clawlet.bus.queue import InboundMessage

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
                SCHED_PAYLOAD_SOURCE: "scheduler",
                SCHED_PAYLOAD_JOB_ID: task.id,
                SCHED_PAYLOAD_RUN_ID: f"sched-{task.id}-{datetime.now(self.timezone).timestamp():.0f}",
                SCHED_PAYLOAD_SESSION_TARGET: task.params.get("session_target", "main"),
                SCHED_PAYLOAD_WAKE_MODE: task.params.get("wake_mode", "now"),
                "agent_id": task.params.get("agent_id"),
                "session_key": task.params.get("session_key"),
            },
        )

        if self._message_bus is None:
            logger.warning(
                f"Scheduler message_bus not configured; cannot enqueue task '{task.name}'"
            )
            return f"Scheduler bus unavailable; task not queued: {task.name}"

        wake_mode = str(task.params.get("wake_mode", "now") or "now").strip().lower()
        if wake_mode == "next-heartbeat":
            wake_mode = "next_heartbeat"
        if wake_mode == "next_heartbeat":
            self._pending_heartbeat_jobs.append(message)
            logger.info(f"Agent task '{task.name}' staged for next heartbeat")
            return f"Agent prompt staged for next heartbeat: {prompt[:100]}..."

        await self._message_bus.publish_inbound(message)
        logger.info(f"Agent task '{task.name}' queued with prompt: {prompt[:100]}...")
        return f"Agent prompt queued: {prompt[:100]}..."

    async def flush_staged_agent_jobs(self) -> int:
        """Publish queued wake_mode=next_heartbeat jobs to message bus."""
        if self._message_bus is None:
            return 0
        if not self._pending_heartbeat_jobs:
            return 0
        staged = list(self._pending_heartbeat_jobs)
        self._pending_heartbeat_jobs.clear()
        for msg in staged:
            await self._message_bus.publish_inbound(msg)
        logger.info(f"Flushed {len(staged)} staged scheduler job(s) on heartbeat tick")
        return len(staged)

    async def on_heartbeat_tick(self, _now: Optional[datetime] = None) -> int:
        """Hook for heartbeat runner to release staged scheduler messages."""
        return await self.flush_staged_agent_jobs()
    
    async def _execute_tool(self, task: ScheduledTask) -> str:
        """Execute a tool."""
        tool_name = task.params.get("tool")
        if not tool_name:
            raise ValueError(f"Task '{task.name}' has no tool name specified")

        registry = self._tool_registry
        if registry is None:
            raise ValueError(
                f"Task '{task.name}' cannot run tool '{tool_name}': tool registry not configured"
            )
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

        registry = self._skill_registry
        if registry is None:
            raise ValueError(
                f"Task '{task.name}' cannot run skill '{skill_name}': skill registry not configured"
            )
        skill = registry.get(skill_name)
        if not skill:
            raise ValueError(f"Skill '{skill_name}' not found")
        
        skill_tool = task.params.get("tool")
        if not skill_tool:
            raise ValueError(f"Task '{task.name}' must set params.tool for skill execution")
        skill_params = task.params.get("params", {})
        result = await skill.execute_tool(skill_tool, **skill_params)
        if hasattr(result, "success") and not getattr(result, "success"):
            err = getattr(result, "error", "") or "Skill execution failed"
            raise ValueError(err)
        if hasattr(result, "output"):
            return str(result.output)
        
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

    async def _deliver_task_result(self, task: ScheduledTask, result: TaskResult) -> None:
        """Apply delivery_mode policy for task execution result."""
        mode = str(task.params.get("delivery_mode", "none") or "none").lower()
        best_effort = bool(task.params.get("best_effort_delivery", False))
        if mode == "none":
            result.metadata["delivery_mode"] = "none"
            result.metadata["delivery_status"] = "not-requested"
            return

        status = "ok" if result.success else "failed"
        summary = (
            f"[scheduler] {task.name} ({task.id}) {status}"
            f" | output={result.output or '-'}"
            f" | error={result.error or '-'}"
        )

        if mode == "announce":
            if self._message_bus is None:
                logger.warning(
                    f"Delivery skipped for task '{task.name}': message bus unavailable"
                )
                result.metadata["delivery_mode"] = "announce"
                result.metadata["delivery_status"] = "not-delivered"
                result.metadata["delivery_error"] = "message bus unavailable"
                return
            from clawlet.bus.queue import OutboundMessage

            channel = str(task.params.get("delivery_channel") or "scheduler")
            chat_id = str(task.params.get("delivery_chat_id") or "main")
            try:
                delivered = await self._message_bus.publish_outbound(
                    OutboundMessage(
                        channel=channel,
                        chat_id=chat_id,
                        content=summary,
                        metadata={
                            SCHED_PAYLOAD_SOURCE: "scheduler",
                            SCHED_PAYLOAD_JOB_ID: task.id,
                            SCHED_PAYLOAD_WAKE_MODE: str(task.params.get("wake_mode", "now")),
                        },
                    )
                )
            except Exception as e:
                if best_effort:
                    logger.warning(f"Announce delivery failed (best effort) for task '{task.name}': {e}")
                    result.metadata["delivery_mode"] = "announce"
                    result.metadata["delivery_status"] = "not-delivered"
                    result.metadata["delivery_error"] = str(e)
                    return
                raise
            result.metadata["delivery_mode"] = "announce"
            result.metadata["delivery_status"] = "delivered" if delivered else "unknown"
            return

        if mode == "webhook":
            url = str(task.params.get("delivery_channel") or task.params.get("webhook_url") or "").strip()
            if not (url.startswith("http://") or url.startswith("https://")):
                logger.warning(
                    f"Webhook delivery skipped for task '{task.name}': invalid URL"
                )
                result.metadata["delivery_mode"] = "webhook"
                result.metadata["delivery_status"] = "not-delivered"
                result.metadata["delivery_error"] = "invalid URL"
                return
            try:
                delivered, delivery_error = await self._post_delivery_webhook(
                    url=url, task=task, result=result, summary=summary
                )
            except Exception as e:
                if best_effort:
                    logger.warning(f"Webhook delivery failed (best effort) for task '{task.name}': {e}")
                    result.metadata["delivery_mode"] = "webhook"
                    result.metadata["delivery_status"] = "not-delivered"
                    result.metadata["delivery_error"] = str(e)
                    return
                raise
            result.metadata["delivery_mode"] = "webhook"
            result.metadata["delivery_status"] = "delivered" if delivered else "not-delivered"
            if delivery_error:
                result.metadata["delivery_error"] = delivery_error
            return

        logger.warning(f"Unknown delivery_mode='{mode}' for task '{task.name}'")
        result.metadata["delivery_mode"] = mode
        result.metadata["delivery_status"] = "unknown"

    async def _maybe_send_failure_alert(self, task: ScheduledTask, result: TaskResult) -> None:
        """Send failure alerts after configurable consecutive failures."""
        alert = task.params.get("failure_alert")
        if not isinstance(alert, dict):
            return
        if not bool(alert.get("enabled", False)):
            return
        after = int(alert.get("after", 3) or 3)
        if after < 1:
            after = 1
        if task.current_attempt < after:
            return
        now = datetime.now(self.timezone)
        cooldown_seconds = int(alert.get("cooldown_seconds", 3600) or 3600)
        last_sent_raw = task.metadata.get("last_failure_alert_at")
        if isinstance(last_sent_raw, str):
            try:
                last_sent = datetime.fromisoformat(last_sent_raw)
                if (now - last_sent).total_seconds() < max(0, cooldown_seconds):
                    return
            except Exception:
                pass
        mode = str(alert.get("mode", "announce") or "announce").lower()
        channel = str(alert.get("channel", "scheduler") or "scheduler")
        to = str(alert.get("to", "main") or "main")
        text = (
            f"[scheduler-alert] job={task.id} name={task.name} failed "
            f"attempt={result.attempt} error={result.error or '-'}"
        )
        sent = False
        if mode == "webhook":
            sent = await self._post_failure_alert_webhook(url=to, payload={"text": text, "job_id": task.id})
        else:
            sent = await self._post_failure_alert_announce(channel=channel, chat_id=to, text=text)
        if sent:
            task.metadata["last_failure_alert_at"] = now.isoformat()

    async def _post_failure_alert_announce(self, channel: str, chat_id: str, text: str) -> bool:
        if self._message_bus is None:
            return False
        from clawlet.bus.queue import OutboundMessage

        return await self._message_bus.publish_outbound(
            OutboundMessage(channel=channel, chat_id=chat_id, content=text, metadata={SCHED_PAYLOAD_SOURCE: "scheduler"})
        )

    async def _post_failure_alert_webhook(self, url: str, payload: dict[str, Any]) -> bool:
        if not (url.startswith("http://") or url.startswith("https://")):
            return False
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    return response.status < 400
        except Exception as e:
            logger.warning(f"Failure alert webhook failed: {e}")
            return False

    async def _post_delivery_webhook(
        self,
        url: str,
        task: ScheduledTask,
        result: TaskResult,
        summary: str,
    ) -> tuple[bool, Optional[str]]:
        import aiohttp

        payload = {
            "job_id": task.id,
            "task_name": task.name,
            "success": result.success,
            "status": result.status.value,
            "output": result.output,
            "error": result.error,
            "summary": summary,
            "completed_at": (result.completed_at or datetime.now(self.timezone)).isoformat(),
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status >= 400:
                    body = await response.text()
                    logger.warning(
                        f"Webhook delivery failed for task '{task.name}': {response.status} {body[:200]}"
                    )
                    return False, f"http {response.status}: {body[:200]}"
        return True, None

    def _persist_jobs_if_configured(self) -> None:
        if self.jobs_file:
            self.save_jobs(self.jobs_file)

    def _persist_state_if_configured(self) -> None:
        if self.state_file:
            self.save_state(self.state_file)

    @staticmethod
    def _safe_job_id(job_id: str) -> str:
        if "/" in job_id or "\\" in job_id:
            raise ValueError(f"Invalid job id for filesystem path: {job_id}")
        return job_id

    def _serialize_task(self, task: ScheduledTask) -> dict[str, Any]:
        interval_seconds = task.interval.total_seconds() if task.interval else None
        one_time = task.one_time.isoformat() if task.one_time else None
        return {
            "id": task.id,
            "name": task.name,
            "cron": task.cron,
            "interval_seconds": interval_seconds,
            "one_time": one_time,
            "timezone": task.timezone,
            "action": task.action.value,
            "params": task.params,
            "enabled": task.enabled,
            "priority": task.priority.name.lower(),
            "depends_on": task.depends_on,
            "notify_on_success": task.notify_on_success,
            "notify_on_failure": task.notify_on_failure,
            "tags": task.tags,
            "retry_policy": {
                "max_attempts": task.retry_policy.max_attempts,
                "delay_seconds": task.retry_policy.delay_seconds,
                "backoff_multiplier": task.retry_policy.backoff_multiplier,
                "max_delay_seconds": task.retry_policy.max_delay_seconds,
            },
        }

    @staticmethod
    def _deserialize_task(task_data: dict[str, Any]) -> ScheduledTask:
        interval = None
        if task_data.get("interval_seconds") is not None:
            interval = timedelta(seconds=float(task_data["interval_seconds"]))
        one_time = None
        if task_data.get("one_time"):
            one_time = datetime.fromisoformat(task_data["one_time"])

        action_name = str(task_data.get("action", "callback")).upper()
        action = TaskAction[action_name]

        retry_raw = task_data.get("retry_policy") or {}
        retry_policy = RetryPolicy(
            max_attempts=int(retry_raw.get("max_attempts", 3)),
            delay_seconds=float(retry_raw.get("delay_seconds", 60.0)),
            backoff_multiplier=float(retry_raw.get("backoff_multiplier", 2.0)),
            max_delay_seconds=float(retry_raw.get("max_delay_seconds", 3600.0)),
        )

        return ScheduledTask(
            id=str(task_data["id"]),
            name=str(task_data.get("name", task_data["id"])),
            cron=task_data.get("cron"),
            interval=interval,
            one_time=one_time,
            timezone=str(task_data.get("timezone", "UTC")),
            action=action,
            params=dict(task_data.get("params") or {}),
            enabled=bool(task_data.get("enabled", True)),
            priority=parse_priority(str(task_data.get("priority", "normal"))),
            depends_on=list(task_data.get("depends_on") or []),
            retry_policy=retry_policy,
            notify_on_success=bool(task_data.get("notify_on_success", False)),
            notify_on_failure=bool(task_data.get("notify_on_failure", True)),
            tags=list(task_data.get("tags") or []),
        )

    def save_jobs(self, path: Path) -> None:
        """Save scheduled job definitions to file."""
        payload = {
            "version": 1,
            "updated_at": datetime.now(self.timezone).isoformat(),
            "jobs": {
                task_id: self._serialize_task(task)
                for task_id, task in self._tasks.items()
            },
        }
        file_path = Path(path).expanduser()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load_jobs(self, path: Path, replace: bool = True) -> int:
        """Load scheduled job definitions from file."""
        file_path = Path(path).expanduser()
        loaded = 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            jobs = payload.get("jobs") or {}
            if replace:
                self._tasks = {}
            for task_id, task_data in jobs.items():
                if not replace and task_id in self._tasks:
                    continue
                task = self._deserialize_task(task_data)
                self._update_next_run(task)
                self._tasks[task.id] = task
                loaded += 1
            logger.debug(f"Loaded {loaded} scheduler jobs from {file_path}")
        except FileNotFoundError:
            logger.debug(f"No scheduler jobs file at {file_path}")
        except Exception as e:
            logger.warning(f"Failed to load scheduler jobs: {e}")
        return loaded

    def _run_log_path(self, task_id: str) -> Optional[Path]:
        if not self.runs_dir:
            return None
        safe_id = self._safe_job_id(task_id)
        runs_dir = self.runs_dir.expanduser()
        runs_dir.mkdir(parents=True, exist_ok=True)
        return runs_dir / f"{safe_id}.jsonl"

    def _record_run(self, task: ScheduledTask, result: TaskResult, trigger: str) -> Optional[Path]:
        run_log_path = self._run_log_path(task.id)
        if run_log_path is None:
            return None
        completed_at = result.completed_at or datetime.now(self.timezone)
        run_entry = {
            "run_id": f"{task.id}-{uuid.uuid4().hex[:12]}",
            "job_id": task.id,
            "task_name": task.name,
            "trigger": trigger,
            "status": result.status.value,
            "success": result.success,
            "attempt": result.attempt,
            "started_at": result.started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": (completed_at - result.started_at).total_seconds(),
            "output": result.output,
            "error": result.error,
            "delivery_mode": result.metadata.get("delivery_mode", "none"),
            "delivery_status": result.metadata.get("delivery_status", "not-requested"),
            "delivery_error": result.metadata.get("delivery_error"),
        }
        with open(run_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(run_entry, ensure_ascii=True))
            f.write("\n")
        return run_log_path

    def list_runs(
        self,
        task_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        delivery_status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return recent run entries for a given task id."""
        run_log_path = self._run_log_path(task_id)
        if run_log_path is None or not run_log_path.exists():
            return []
        with open(run_log_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        entries: list[dict[str, Any]] = []
        for line in lines:
            try:
                entry = json.loads(line)
                if status and str(entry.get("status")) != status:
                    continue
                if delivery_status and str(entry.get("delivery_status")) != delivery_status:
                    continue
                entries.append(entry)
            except json.JSONDecodeError:
                continue
        entries.sort(key=lambda e: str(e.get("completed_at") or ""), reverse=True)
        if offset > 0:
            entries = entries[offset:]
        if limit > 0:
            entries = entries[:limit]
        return entries

    def list_all_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        delivery_status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return recent run entries across all jobs."""
        if not self.runs_dir:
            return []
        runs_dir = self.runs_dir.expanduser()
        if not runs_dir.exists():
            return []
        entries: list[dict[str, Any]] = []
        for run_log_path in runs_dir.glob("*.jsonl"):
            try:
                with open(run_log_path, "r", encoding="utf-8") as f:
                    for raw in f:
                        line = raw.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if status and str(entry.get("status")) != status:
                            continue
                        if delivery_status and str(entry.get("delivery_status")) != delivery_status:
                            continue
                        entries.append(entry)
            except Exception:
                continue
        entries.sort(key=lambda e: str(e.get("completed_at") or ""), reverse=True)
        if offset > 0:
            entries = entries[offset:]
        if limit > 0:
            entries = entries[:limit]
        return entries
    
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
                    "delivery_mode": (task.last_result.metadata or {}).get("delivery_mode")
                    if task.last_result
                    else None,
                    "delivery_status": (task.last_result.metadata or {}).get("delivery_status")
                    if task.last_result
                    else None,
                    "delivery_error": (task.last_result.metadata or {}).get("delivery_error")
                    if task.last_result
                    else None,
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
                        "metadata": task.last_result.metadata or {},
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
                            metadata=dict(task_state["last_result"].get("metadata") or {}),
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
    if config.checks:
        params["checks"] = list(config.checks)
    if getattr(config, "agent_id", None):
        params["agent_id"] = config.agent_id
    if getattr(config, "session_key", None):
        params["session_key"] = config.session_key
    params["session_target"] = getattr(config, "session_target", "main")
    params["wake_mode"] = getattr(config, "wake_mode", "now")
    params["delivery_mode"] = getattr(config, "delivery_mode", "none")
    params["best_effort_delivery"] = bool(getattr(config, "best_effort_delivery", False))
    params["delete_after_run"] = bool(getattr(config, "delete_after_run", False))
    if getattr(config, "delivery_channel", None):
        params["delivery_channel"] = config.delivery_channel
    failure_alert = getattr(config, "failure_alert", None)
    if failure_alert and getattr(failure_alert, "enabled", False):
        params["failure_alert"] = {
            "enabled": True,
            "after": int(getattr(failure_alert, "after", 3)),
            "cooldown_seconds": int(getattr(failure_alert, "cooldown_seconds", 3600)),
            "mode": str(getattr(failure_alert, "mode", "announce")),
            "channel": str(getattr(failure_alert, "channel", "scheduler")),
            "to": str(getattr(failure_alert, "to", "main")),
        }
    
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
