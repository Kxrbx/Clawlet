"""
Dashboard module - Web UI and API server.
"""

from clawlet.dashboard.api import (
    app,
    start_dashboard_server,
    agent_status,
)

__all__ = [
    "app",
    "start_dashboard_server",
    "agent_status",
]
