"""
Heartbeat runner service.

Publishes synthetic inbound messages on a fixed cadence so the agent can
perform periodic proactive checks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

from loguru import logger

from clawlet.bus.queue import InboundMessage, MessageBus
from clawlet.metrics import get_metrics
from clawlet.runtime.events import (
    SCHED_PAYLOAD_JOB_ID,
    SCHED_PAYLOAD_RUN_ID,
    SCHED_PAYLOAD_SESSION_TARGET,
    SCHED_PAYLOAD_SOURCE,
    SCHED_PAYLOAD_WAKE_MODE,
)

UTC = timezone.utc


@dataclass
class LastRoute:
    """Best-effort route information for heartbeat target='last'."""

    channel: str
    chat_id: str
    user_id: str = ""
    user_name: str = ""


class HeartbeatRunner:
    """Publishes heartbeat prompts to the agent message bus."""

    def __init__(
        self,
        bus: MessageBus,
        interval_minutes: int,
        quiet_hours_start: int,
        quiet_hours_end: int,
        target: str = "last",
        ack_max_chars: int = 24,
        route_provider: Optional[Callable[[], Optional[object]]] = None,
        heartbeat_context: str = "",
        on_tick: Optional[Callable[[datetime], Awaitable[Any]]] = None,
    ):
        self.bus = bus
        self.interval_minutes = max(1, int(interval_minutes))
        self.quiet_hours_start = int(quiet_hours_start)
        self.quiet_hours_end = int(quiet_hours_end)
        self.target = target
        self.ack_max_chars = max(1, int(ack_max_chars))
        self.route_provider = route_provider
        self.heartbeat_context = heartbeat_context.strip()
        self.on_tick = on_tick
        self._running = False

    async def start(self) -> None:
        """Run heartbeat loop until stopped."""
        self._running = True
        logger.info(
            f"Heartbeat runner started (every={self.interval_minutes}m, target={self.target})"
        )
        next_run = datetime.now(UTC)

        while self._running:
            now = datetime.now(UTC)
            if now >= next_run:
                try:
                    await self._tick(now)
                except Exception as e:
                    logger.error(f"Heartbeat tick failed: {e}")
                next_run = now + timedelta(minutes=self.interval_minutes)

            # Keep stop latency low even for long intervals.
            await asyncio.sleep(1.0)

    def stop(self) -> None:
        """Stop the heartbeat loop."""
        self._running = False
        logger.info("Heartbeat runner stopping")

    async def _tick(self, now: datetime) -> None:
        if self._is_quiet_hour(now):
            logger.debug("Heartbeat skipped due to quiet hours")
            return

        if self.on_tick is not None:
            try:
                await self.on_tick(now)
            except Exception as e:
                logger.warning(f"Heartbeat on_tick hook failed: {e}")

        route = self._resolve_route()
        if route is None:
            logger.debug("Heartbeat skipped: no routable target")
            return

        get_metrics().inc_heartbeat_ticks()
        prompt = self._build_prompt()
        await self.bus.publish_inbound(
            InboundMessage(
                channel=route.channel,
                chat_id=route.chat_id,
                content=prompt,
                user_id=route.user_id or "heartbeat",
                user_name=route.user_name or "Heartbeat",
                metadata={
                    "source": "heartbeat",
                    "heartbeat": True,
                    "heartbeat_tick_at": now.isoformat(),
                    "ack_max_chars": self.ack_max_chars,
                    SCHED_PAYLOAD_JOB_ID: "heartbeat",
                    SCHED_PAYLOAD_RUN_ID: f"hb-{uuid4().hex[:12]}",
                    SCHED_PAYLOAD_SOURCE: "heartbeat",
                    SCHED_PAYLOAD_SESSION_TARGET: "main",
                    SCHED_PAYLOAD_WAKE_MODE: "next_heartbeat",
                },
            )
        )
        logger.info(f"Heartbeat tick published to {route.channel}/{route.chat_id}")

    def _resolve_route(self) -> Optional[LastRoute]:
        if self.target == "main":
            return LastRoute(channel="scheduler", chat_id="main")
        if self.target == "last" and self.route_provider is not None:
            route = self.route_provider()
            if route is None:
                return None
            if isinstance(route, LastRoute):
                return route
            if isinstance(route, dict):
                ch = str(route.get("channel") or "")
                cid = str(route.get("chat_id") or "")
                if not ch or not cid:
                    return None
                return LastRoute(
                    channel=ch,
                    chat_id=cid,
                    user_id=str(route.get("user_id") or ""),
                    user_name=str(route.get("user_name") or ""),
                )
        return None

    def _is_quiet_hour(self, now: datetime) -> bool:
        hour = now.hour
        start = self.quiet_hours_start
        end = self.quiet_hours_end
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def _build_prompt(self) -> str:
        base = (
            "Heartbeat check: perform one meaningful proactive action if possible. "
            "If there is nothing actionable, respond exactly with HEARTBEAT_OK."
        )
        if self.heartbeat_context:
            return f"{base}\n\nHEARTBEAT_CONTEXT:\n{self.heartbeat_context[:4000]}"
        return base
