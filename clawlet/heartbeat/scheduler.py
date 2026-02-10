"""
Heartbeat scheduler for periodic tasks.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional, Any
from enum import Enum
import json

from loguru import logger


class HeartbeatPriority(Enum):
    """Priority levels for heartbeat tasks."""
    LOW = 1
    NORMAL = 2
    HIGH = 3


@dataclass
class HeartbeatTask:
    """A periodic task to run during heartbeats."""
    name: str
    callback: Callable[[], Any]
    interval_seconds: float = 7200  # Default: 2 hours
    priority: HeartbeatPriority = HeartbeatPriority.NORMAL
    last_run: Optional[datetime] = None
    enabled: bool = True
    last_result: Optional[str] = None
    
    def should_run(self, now: datetime) -> bool:
        """Check if this task should run."""
        if not self.enabled:
            return False
        if self.last_run is None:
            return True
        elapsed = (now - self.last_run).total_seconds()
        return elapsed >= self.interval_seconds


class HeartbeatScheduler:
    """
    Scheduler for periodic heartbeat tasks.
    
    This enables the agent to perform autonomous actions
    like checking messages, browsing feeds, etc.
    """
    
    def __init__(self, check_interval: float = 60.0):
        """
        Initialize the heartbeat scheduler.
        
        Args:
            check_interval: How often to check for pending tasks (seconds)
        """
        self.check_interval = check_interval
        self._tasks: dict[str, HeartbeatTask] = {}
        self._running = False
        self._state_file: Optional[str] = None
        
        logger.info(f"HeartbeatScheduler initialized with check_interval={check_interval}s")
    
    def register(
        self,
        name: str,
        callback: Callable[[], Any],
        interval_seconds: float = 7200,
        priority: HeartbeatPriority = HeartbeatPriority.NORMAL,
    ) -> None:
        """
        Register a heartbeat task.
        
        Args:
            name: Unique task name
            callback: Async or sync function to call
            interval_seconds: How often to run (default: 2 hours)
            priority: Task priority (affects execution order)
        """
        task = HeartbeatTask(
            name=name,
            callback=callback,
            interval_seconds=interval_seconds,
            priority=priority,
        )
        self._tasks[name] = task
        logger.info(f"Registered heartbeat task: {name} (every {interval_seconds}s)")
    
    def unregister(self, name: str) -> None:
        """Remove a task."""
        if name in self._tasks:
            del self._tasks[name]
            logger.info(f"Unregistered heartbeat task: {name}")
    
    def enable(self, name: str) -> None:
        """Enable a task."""
        if name in self._tasks:
            self._tasks[name].enabled = True
    
    def disable(self, name: str) -> None:
        """Disable a task."""
        if name in self._tasks:
            self._tasks[name].enabled = False
    
    async def run(self) -> None:
        """Run the scheduler loop."""
        self._running = True
        logger.info("Heartbeat scheduler started")
        
        while self._running:
            try:
                await self._check_and_run_tasks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("Heartbeat scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in heartbeat scheduler: {e}")
                await asyncio.sleep(self.check_interval)
    
    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        logger.info("Heartbeat scheduler stopping")
    
    async def _check_and_run_tasks(self) -> None:
        """Check for pending tasks and run them."""
        now = datetime.utcnow()
        
        # Sort by priority (high first)
        pending = [
            task for task in self._tasks.values()
            if task.should_run(now)
        ]
        pending.sort(key=lambda t: t.priority.value, reverse=True)
        
        if not pending:
            return
        
        logger.info(f"Running {len(pending)} heartbeat task(s)")
        
        for task in pending:
            try:
                result = await self._run_task(task)
                task.last_run = now
                task.last_result = result
                logger.info(f"Heartbeat task '{task.name}' completed: {result[:100] if result else 'OK'}")
            except Exception as e:
                logger.error(f"Heartbeat task '{task.name}' failed: {e}")
                task.last_result = f"ERROR: {e}"
    
    async def _run_task(self, task: HeartbeatTask) -> Optional[str]:
        """Run a single task."""
        callback = task.callback
        
        # Support both sync and async callbacks
        if asyncio.iscoroutinefunction(callback):
            result = await callback()
        else:
            result = callback()
        
        # Convert result to string
        if result is None:
            return None
        if isinstance(result, str):
            return result
        return str(result)
    
    def get_status(self) -> dict:
        """Get scheduler status."""
        now = datetime.utcnow()
        
        tasks_status = []
        for task in self._tasks.values():
            next_run = None
            if task.last_run:
                elapsed = (now - task.last_run).total_seconds()
                remaining = task.interval_seconds - elapsed
                next_run = max(0, remaining)
            else:
                next_run = 0
            
            tasks_status.append({
                "name": task.name,
                "enabled": task.enabled,
                "priority": task.priority.name,
                "interval_seconds": task.interval_seconds,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "next_run_in": next_run,
                "last_result": task.last_result[:200] if task.last_result else None,
            })
        
        return {
            "running": self._running,
            "check_interval": self.check_interval,
            "total_tasks": len(self._tasks),
            "enabled_tasks": sum(1 for t in self._tasks.values() if t.enabled),
            "tasks": tasks_status,
        }
    
    def save_state(self, path: str) -> None:
        """Save scheduler state to file."""
        state = {
            "tasks": {
                name: {
                    "last_run": task.last_run.isoformat() if task.last_run else None,
                    "last_result": task.last_result,
                }
                for name, task in self._tasks.items()
            }
        }
        
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
        
        logger.debug(f"Saved heartbeat state to {path}")
    
    def load_state(self, path: str) -> None:
        """Load scheduler state from file."""
        try:
            with open(path, "r") as f:
                state = json.load(f)
            
            for name, task_state in state.get("tasks", {}).items():
                if name in self._tasks:
                    if task_state.get("last_run"):
                        self._tasks[name].last_run = datetime.fromisoformat(task_state["last_run"])
                    self._tasks[name].last_result = task_state.get("last_result")
            
            logger.debug(f"Loaded heartbeat state from {path}")
        except FileNotFoundError:
            logger.debug(f"No heartbeat state file at {path}")
        except Exception as e:
            logger.warning(f"Failed to load heartbeat state: {e}")
