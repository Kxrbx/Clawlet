"""
Metrics collection for Clawlet agent.
Provides Prometheus-style metrics for monitoring.
"""

import time
from dataclasses import dataclass
from typing import Optional

class Counters:
    def __init__(self):
        self._messages_total = 0
        self._errors_total = 0
        self._tool_errors_total = 0
        self._storage_errors_total = 0
        self._heartbeat_ticks_total = 0
        self._heartbeat_acks_suppressed_total = 0
        self._scheduled_runs_attempted_total = 0
        self._scheduled_runs_succeeded_total = 0
        self._scheduled_runs_failed_total = 0
        self._proactive_tasks_completed_total = 0
        self._start_time = time.time()
    
    def inc_messages(self):
        self._messages_total += 1
    
    def inc_errors(self):
        self._errors_total += 1
    
    def inc_tool_errors(self):
        self._tool_errors_total += 1
    
    def inc_storage_errors(self):
        self._storage_errors_total += 1

    def inc_heartbeat_ticks(self):
        self._heartbeat_ticks_total += 1

    def inc_heartbeat_acks_suppressed(self):
        self._heartbeat_acks_suppressed_total += 1

    def inc_scheduled_runs_attempted(self):
        self._scheduled_runs_attempted_total += 1

    def inc_scheduled_runs_succeeded(self):
        self._scheduled_runs_succeeded_total += 1

    def inc_scheduled_runs_failed(self):
        self._scheduled_runs_failed_total += 1

    def inc_proactive_tasks_completed(self):
        self._proactive_tasks_completed_total += 1
    
    @property
    def messages_total(self) -> int:
        return self._messages_total
    
    @property
    def errors_total(self) -> int:
        return self._errors_total
    
    @property
    def tool_errors_total(self) -> int:
        return self._tool_errors_total
    
    @property
    def storage_errors_total(self) -> int:
        return self._storage_errors_total

    @property
    def heartbeat_ticks_total(self) -> int:
        return self._heartbeat_ticks_total

    @property
    def heartbeat_acks_suppressed_total(self) -> int:
        return self._heartbeat_acks_suppressed_total

    @property
    def scheduled_runs_attempted_total(self) -> int:
        return self._scheduled_runs_attempted_total

    @property
    def scheduled_runs_succeeded_total(self) -> int:
        return self._scheduled_runs_succeeded_total

    @property
    def scheduled_runs_failed_total(self) -> int:
        return self._scheduled_runs_failed_total

    @property
    def proactive_tasks_completed_total(self) -> int:
        return self._proactive_tasks_completed_total
    
    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time


# Global metrics instance (per agent process)
_metrics: Optional[Counters] = None

def get_metrics() -> Counters:
    global _metrics
    if _metrics is None:
        _metrics = Counters()
    return _metrics

def reset_metrics():
    global _metrics
    _metrics = Counters()

def format_prometheus() -> str:
    m = get_metrics()
    lines = [
        "# HELP clawlet_messages_total Total number of messages processed",
        "# TYPE clawlet_messages_total counter",
        f"clawlet_messages_total {m.messages_total}",
        "# HELP clawlet_errors_total Total number of errors encountered",
        "# TYPE clawlet_errors_total counter",
        f"clawlet_errors_total {m.errors_total}",
        "# HELP clawlet_tool_errors_total Total number of tool execution errors",
        "# TYPE clawlet_tool_errors_total counter",
        f"clawlet_tool_errors_total {m.tool_errors_total}",
        "# HELP clawlet_storage_errors_total Total number of storage persistence errors",
        "# TYPE clawlet_storage_errors_total counter",
        f"clawlet_storage_errors_total {m.storage_errors_total}",
        "# HELP clawlet_uptime_seconds Agent uptime in seconds",
        "# TYPE clawlet_uptime_seconds gauge",
        f"clawlet_uptime_seconds {m.uptime_seconds:.2f}",
        "# HELP clawlet_heartbeat_ticks_total Total number of heartbeat ticks published",
        "# TYPE clawlet_heartbeat_ticks_total counter",
        f"clawlet_heartbeat_ticks_total {m.heartbeat_ticks_total}",
        "# HELP clawlet_heartbeat_acks_suppressed_total Total number of trivial heartbeat responses suppressed",
        "# TYPE clawlet_heartbeat_acks_suppressed_total counter",
        f"clawlet_heartbeat_acks_suppressed_total {m.heartbeat_acks_suppressed_total}",
        "# HELP clawlet_scheduled_runs_attempted_total Total number of scheduled runs attempted",
        "# TYPE clawlet_scheduled_runs_attempted_total counter",
        f"clawlet_scheduled_runs_attempted_total {m.scheduled_runs_attempted_total}",
        "# HELP clawlet_scheduled_runs_succeeded_total Total number of scheduled runs succeeded",
        "# TYPE clawlet_scheduled_runs_succeeded_total counter",
        f"clawlet_scheduled_runs_succeeded_total {m.scheduled_runs_succeeded_total}",
        "# HELP clawlet_scheduled_runs_failed_total Total number of scheduled runs failed",
        "# TYPE clawlet_scheduled_runs_failed_total counter",
        f"clawlet_scheduled_runs_failed_total {m.scheduled_runs_failed_total}",
        "# HELP clawlet_proactive_tasks_completed_total Total number of proactive tasks completed",
        "# TYPE clawlet_proactive_tasks_completed_total counter",
        f"clawlet_proactive_tasks_completed_total {m.proactive_tasks_completed_total}",
    ]
    return "\n".join(lines)
