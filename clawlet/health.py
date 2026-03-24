"""
Health check system for monitoring agent status.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum
import json
from pathlib import Path

import yaml

from loguru import logger
from clawlet.cli.runtime_paths import get_default_workspace_path, get_workspace_layout_for


class HealthStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str
    latency_ms: Optional[float] = None
    details: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "details": self.details or {},
        }


class HealthChecker:
    """
    System for checking health of various components.
    
    Checks:
    - Provider connectivity
    - Storage backend
    - Channel connections
    - Memory usage
    """
    
    def __init__(
        self,
        provider=None,
        storage=None,
        channels: dict = None,
    ):
        self.provider = provider
        self.storage = storage
        self.channels = channels or {}
    
    async def check_all(self) -> dict:
        """
        Run all health checks.
        
        Returns:
            Dict with overall status and individual check results
        """
        results = []
        
        # Run checks in parallel
        checks = [
            self.check_provider(),
            self.check_storage(),
            self.check_memory(),
        ]
        
        # Add channel checks
        for name, channel in self.channels.items():
            checks.append(self.check_channel(name, channel))
        
        check_results = await asyncio.gather(*checks, return_exceptions=True)
        
        for result in check_results:
            if isinstance(result, Exception):
                results.append(HealthCheckResult(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {result}",
                ))
            else:
                results.append(result)
        
        # Determine overall status
        statuses = [r.status for r in results]
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall = HealthStatus.UNHEALTHY
        else:
            overall = HealthStatus.DEGRADED
        
        return {
            "status": overall.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": [r.to_dict() for r in results],
        }
    
    async def check_provider(self) -> HealthCheckResult:
        """Check LLM provider health."""
        if not self.provider:
            return HealthCheckResult(
                name="provider",
                status=HealthStatus.UNHEALTHY,
                message="No provider configured",
            )
        
        start = datetime.now(timezone.utc)
        
        try:
            # Try a minimal completion
            # This is a simple ping - providers may have better health endpoints
            response = await asyncio.wait_for(
                self.provider.complete(
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=5,
                ),
                timeout=5.0,
            )
            
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            
            return HealthCheckResult(
                name="provider",
                status=HealthStatus.HEALTHY,
                message=f"Provider {self.provider.name} responding",
                latency_ms=latency,
                details={"model": self.provider.get_default_model()},
            )
            
        except asyncio.TimeoutError:
            return HealthCheckResult(
                name="provider",
                status=HealthStatus.UNHEALTHY,
                message="Provider timeout (>5s)",
            )
        except Exception as e:
            return HealthCheckResult(
                name="provider",
                status=HealthStatus.UNHEALTHY,
                message=f"Provider error: {e}",
            )
    
    async def check_storage(self) -> HealthCheckResult:
        """Check storage backend health."""
        if not self.storage:
            return HealthCheckResult(
                name="storage",
                status=HealthStatus.DEGRADED,
                message="No storage configured (using in-memory)",
            )
        
        start = datetime.now(timezone.utc)
        
        try:
            # Try a simple read operation
            # Storage backends should implement a health check method
            if hasattr(self.storage, 'health_check'):
                await self.storage.health_check()
            else:
                # Fallback - try to read something
                pass
            
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            
            backend_type = type(self.storage).__name__
            
            return HealthCheckResult(
                name="storage",
                status=HealthStatus.HEALTHY,
                message=f"Storage {backend_type} responding",
                latency_ms=latency,
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="storage",
                status=HealthStatus.UNHEALTHY,
                message=f"Storage error: {e}",
            )
    
    async def check_channel(self, name: str, channel) -> HealthCheckResult:
        """Check a channel's health."""
        if not channel:
            return HealthCheckResult(
                name=f"channel_{name}",
                status=HealthStatus.DEGRADED,
                message=f"Channel {name} not configured",
            )
        
        try:
            # Check if channel has a running bot/client
            if hasattr(channel, 'bot') and hasattr(channel.bot, 'is_ready'):
                if channel.bot.is_ready():
                    return HealthCheckResult(
                        name=f"channel_{name}",
                        status=HealthStatus.HEALTHY,
                        message=f"Channel {name} connected",
                    )
            
            # Generic check
            return HealthCheckResult(
                name=f"channel_{name}",
                status=HealthStatus.DEGRADED,
                message=f"Channel {name} status unknown",
            )
            
        except Exception as e:
            return HealthCheckResult(
                name=f"channel_{name}",
                status=HealthStatus.UNHEALTHY,
                message=f"Channel {name} error: {e}",
            )
    
    async def check_memory(self) -> HealthCheckResult:
        """Check system memory usage."""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            
            if memory.percent > 90:
                status = HealthStatus.UNHEALTHY
                message = f"Memory critical: {memory.percent}% used"
            elif memory.percent > 75:
                status = HealthStatus.DEGRADED
                message = f"Memory high: {memory.percent}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory OK: {memory.percent}% used"
            
            return HealthCheckResult(
                name="memory",
                status=status,
                message=message,
                details={
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "percent": memory.percent,
                },
            )
            
        except ImportError:
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.HEALTHY,
                message="Memory check skipped (psutil not installed)",
            )
        except Exception as e:
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.DEGRADED,
                message=f"Memory check error: {e}",
            )


async def quick_health_check() -> dict:
    """
    Quick health check without dependencies.
    
    Returns basic system status.
    """
    checks = [
        {
            "name": "system",
            "status": "healthy",
            "message": "System operational",
        }
    ]
    overall = "healthy"

    workspace = get_default_workspace_path()
    config_path = workspace / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            scheduler = raw.get("scheduler") or {}
            heartbeat = raw.get("heartbeat") or {}
            tasks = (scheduler.get("tasks") or {}) if isinstance(scheduler, dict) else {}

            layout = get_workspace_layout_for(workspace)
            runs_dir = Path(str(scheduler.get("runs_dir") or (layout.root / "cron" / "runs"))).expanduser()
            if not runs_dir.is_absolute():
                runs_dir = layout.root / runs_dir
            failed_recent = 0
            total_recent = 0
            if runs_dir.exists():
                for run_file in runs_dir.glob("*.jsonl"):
                    with open(run_file, "r", encoding="utf-8") as f:
                        lines = [ln.strip() for ln in f if ln.strip()]
                    for line in lines[-10:]:
                        total_recent += 1
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if str(entry.get("status")) == "failed":
                            failed_recent += 1

            queue_backlog = 0
            queue_path = Path(str(heartbeat.get("proactive_queue_path") or "tasks/QUEUE.md"))
            if not queue_path.is_absolute():
                queue_path = workspace / queue_path
            if queue_path.exists():
                text = queue_path.read_text(encoding="utf-8")
                queue_backlog = sum(1 for ln in text.splitlines() if "- [ ]" in ln)

            status = "healthy"
            msg = f"tasks={len(tasks)} backlog={queue_backlog} failed_recent={failed_recent}/{total_recent}"
            if failed_recent >= 3:
                status = "degraded"
                msg = f"Repeated scheduler failures detected: {msg}"
            elif queue_backlog >= 20:
                status = "degraded"
                msg = f"Proactive backlog growth detected: {msg}"
            checks.append({"name": "automation", "status": status, "message": msg})
            if status != "healthy":
                overall = "degraded"
        except Exception as e:
            checks.append(
                {
                    "name": "automation",
                    "status": "degraded",
                    "message": f"Automation health check error: {e}",
                }
            )
            overall = "degraded"

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


def quick_runtime_doctor(workspace: Optional[Path] = None) -> dict:
    """Inspect recent runtime artifacts for common reliability failures."""
    workspace = workspace or get_default_workspace_path()
    layout = get_workspace_layout_for(workspace)
    events_path = layout.runtime_dir / "events.jsonl"
    heartbeat_state_path = layout.heartbeat_state_path

    checks: list[dict] = []
    overall = "healthy"

    last_provider_failed: dict | None = None
    last_channel_failed: dict | None = None
    placeholder_calls = 0
    over_budget_runs = 0
    recent_event_count = 0
    started_run_ids: set[str] = set()
    completed_run_ids: set[str] = set()

    if events_path.exists():
        try:
            lines = events_path.read_text(encoding="utf-8").splitlines()[-300:]
            recent_event_count = len(lines)
            for raw in lines:
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                event_type = str(event.get("event_type") or "")
                payload = event.get("payload") or {}
                text_payload = json.dumps(payload, ensure_ascii=False)
                if '"the live value"' in text_payload or '"auth_profile": "the live value"' in text_payload:
                    placeholder_calls += 1
                if event_type == "ProviderFailed":
                    last_provider_failed = event
                elif event_type == "ChannelFailed":
                    last_channel_failed = event
                elif event_type == "RunStarted":
                    started_run_ids.add(str(event.get("run_id") or ""))
                elif event_type == "RunCompleted":
                    completed_run_ids.add(str(event.get("run_id") or ""))
                    preview = str(payload.get("response_preview") or "").lower()
                    if "excessive tool calls" in preview or "maximum number of iterations" in preview:
                        over_budget_runs += 1
        except Exception as e:
            checks.append({"name": "runtime_events", "status": "degraded", "message": f"Could not inspect runtime events: {e}"})
            overall = "degraded"
    else:
        checks.append({"name": "runtime_events", "status": "degraded", "message": "No runtime event log found"})
        overall = "degraded"

    if last_provider_failed is not None:
        payload = last_provider_failed.get("payload") or {}
        checks.append(
            {
                "name": "provider_failures",
                "status": "degraded",
                "message": f"Last provider failure: {payload.get('failure_code', 'unknown')} ({payload.get('provider', 'unknown')})",
                "details": {"timestamp": last_provider_failed.get("timestamp", ""), "attempt": payload.get("attempt", 0)},
            }
        )
        overall = "degraded"
    else:
        checks.append({"name": "provider_failures", "status": "healthy", "message": "No recent provider failures"})

    if last_channel_failed is not None:
        payload = last_channel_failed.get("payload") or {}
        checks.append(
            {
                "name": "channel_failures",
                "status": "unhealthy",
                "message": f"Last channel failure: {payload.get('failure_code', 'unknown')}",
                "details": {"timestamp": last_channel_failed.get("timestamp", "")},
            }
        )
        overall = "unhealthy"
    else:
        checks.append({"name": "channel_failures", "status": "healthy", "message": "No recent channel failures"})

    if placeholder_calls:
        checks.append(
            {
                "name": "placeholder_artifacts",
                "status": "degraded",
                "message": f"Detected {placeholder_calls} recent tool payload(s) with placeholder artifacts",
                "details": {"recent_events_scanned": recent_event_count},
            }
        )
        if overall == "healthy":
            overall = "degraded"
    else:
        checks.append({"name": "placeholder_artifacts", "status": "healthy", "message": "No recent placeholder tool payloads"})

    if over_budget_runs:
        checks.append(
            {
                "name": "run_budgets",
                "status": "degraded",
                "message": f"Detected {over_budget_runs} recent run(s) that exhausted iteration/tool-call budget",
            }
        )
        if overall == "healthy":
            overall = "degraded"
    else:
        checks.append({"name": "run_budgets", "status": "healthy", "message": "No recent over-budget runs"})

    orphaned_runs = sorted(run_id for run_id in started_run_ids if run_id and run_id not in completed_run_ids)
    if orphaned_runs:
        checks.append(
            {
                "name": "run_lifecycle",
                "status": "degraded",
                "message": f"Detected {len(orphaned_runs)} started run(s) without RunCompleted in recent event window",
                "details": {"sample_run_id": orphaned_runs[0]},
            }
        )
        if overall == "healthy":
            overall = "degraded"
    else:
        checks.append({"name": "run_lifecycle", "status": "healthy", "message": "No recent orphaned runs"})

    if heartbeat_state_path.exists():
        try:
            state = json.loads(heartbeat_state_path.read_text(encoding="utf-8"))
            outcome_kind = str(state.get("last_outcome_kind") or "")
            last_result = str(state.get("last_result") or "")
            status = "healthy"
            message = "Heartbeat state looks coherent"
            if outcome_kind == "ok" and last_result.startswith("HEARTBEAT_BLOCKED"):
                status = "unhealthy"
                message = "Heartbeat state is incoherent: ok outcome with blocked result text"
            elif outcome_kind == "blocked" and not last_result.startswith("HEARTBEAT_BLOCKED"):
                status = "degraded"
                message = "Heartbeat state kind/result mismatch"
            elif outcome_kind == "degraded":
                status = "degraded"
                message = "Heartbeat recently degraded"
            checks.append({"name": "heartbeat_state", "status": status, "message": message})
            if status == "unhealthy":
                overall = "unhealthy"
            elif status == "degraded" and overall == "healthy":
                overall = "degraded"
        except Exception as e:
            checks.append({"name": "heartbeat_state", "status": "degraded", "message": f"Could not inspect heartbeat state: {e}"})
            if overall == "healthy":
                overall = "degraded"

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
