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
        self._start_time = time.time()
    
    def inc_messages(self):
        self._messages_total += 1
    
    def inc_errors(self):
        self._errors_total += 1
    
    def inc_tool_errors(self):
        self._tool_errors_total += 1
    
    def inc_storage_errors(self):
        self._storage_errors_total += 1
    
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
    ]
    return "\n".join(lines)
