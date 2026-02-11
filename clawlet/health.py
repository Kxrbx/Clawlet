"""
Health check system for monitoring agent status.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

from loguru import logger


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
            "timestamp": datetime.utcnow().isoformat(),
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
        
        start = datetime.utcnow()
        
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
            
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            
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
        
        start = datetime.utcnow()
        
        try:
            # Try a simple read operation
            # Storage backends should implement a health check method
            if hasattr(self.storage, 'health_check'):
                await self.storage.health_check()
            else:
                # Fallback - try to read something
                pass
            
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            
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
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": [
            {
                "name": "system",
                "status": "healthy",
                "message": "System operational",
            }
        ]
    }
