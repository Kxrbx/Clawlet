"""
Heartbeat runner service.

Publishes synthetic inbound messages on a fixed cadence so the agent can
perform periodic proactive checks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

from loguru import logger

from clawlet.bus.queue import InboundMessage, MessageBus
from clawlet.heartbeat.state import HeartbeatStateStore
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
    DEFAULT_PROMPT = (
        "Read HEARTBEAT.md if it exists (workspace context). "
        "Follow it strictly. Do not infer or repeat old tasks from prior chats. "
        "If nothing needs attention, reply HEARTBEAT_OK."
    )

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
        heartbeat_context_provider: Optional[Callable[[], str]] = None,
        state_path: Optional[Path] = None,
        heartbeat_state_path: Optional[Path] = None,
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
        self.heartbeat_context_provider = heartbeat_context_provider
        self.state_path = Path(state_path) if state_path is not None else None
        self.heartbeat_state = HeartbeatStateStore(
            Path(heartbeat_state_path) if heartbeat_state_path is not None else Path.cwd() / "memory" / "heartbeat-state.json"
        )
        self.on_tick = on_tick
        self._running = False

    async def start(self) -> None:
        """Run heartbeat loop until stopped."""
        self._running = True
        logger.info(
            f"Heartbeat runner started (every={self.interval_minutes}m, target={self.target})"
        )
        next_run = self._compute_initial_next_run(datetime.now(UTC))

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

    def _compute_initial_next_run(self, now: datetime) -> datetime:
        """Resume cadence from persisted state instead of forcing an immediate boot tick."""
        state = self.heartbeat_state.load()
        last_tick = self._parse_state_dt(state.get("last_tick_at", ""))
        if last_tick is None:
            return now + timedelta(minutes=self.interval_minutes)
        next_due = last_tick + timedelta(minutes=self.interval_minutes)
        if next_due <= now:
            return now + timedelta(minutes=self.interval_minutes)
        return next_due

    def stop(self) -> None:
        """Stop the heartbeat loop."""
        self._running = False
        logger.info("Heartbeat runner stopping")

    async def _tick(self, now: datetime) -> None:
        if self._is_quiet_hour(now):
            logger.debug("Heartbeat skipped due to quiet hours")
            self._persist_state(now=now, status="skipped", reason="quiet_hours")
            self.heartbeat_state.record_runner_decision(now=now, status="skipped", reason="quiet_hours")
            return

        if self.on_tick is not None:
            try:
                await self.on_tick(now)
            except Exception as e:
                logger.warning(f"Heartbeat on_tick hook failed: {e}")

        heartbeat_context = self._get_heartbeat_context()
        if not self._has_actionable_heartbeat_context(heartbeat_context):
            logger.debug("Heartbeat skipped: HEARTBEAT.md has no actionable content")
            self._persist_state(now=now, status="skipped", reason="no_actionable_context")
            self.heartbeat_state.record_runner_decision(
                now=now,
                status="skipped",
                reason="no_actionable_context",
            )
            return

        route = self._resolve_route()
        route_payload = {"channel": route.channel, "chat_id": route.chat_id} if route is not None else None
        decision = self.heartbeat_state.evaluate_tick(
            now=now,
            context=heartbeat_context,
            route=route_payload,
            interval_minutes=self.interval_minutes,
        )
        if not decision.should_publish:
            logger.debug(f"Heartbeat skipped: {decision.reason}")
            self._persist_state(now=now, status="skipped", reason=decision.reason, route=decision.route)
            self.heartbeat_state.record_runner_decision(
                now=now,
                status="skipped",
                reason=decision.reason,
                route=decision.route,
                check_types=decision.check_types,
                due_checks=decision.due_checks,
            )
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
                    "heartbeat_check_types": list(decision.check_types),
                    "heartbeat_due_checks": list(decision.due_checks),
                    "heartbeat_state_summary": self.heartbeat_state.build_prompt_summary(now),
                    SCHED_PAYLOAD_JOB_ID: "heartbeat",
                    SCHED_PAYLOAD_RUN_ID: f"hb-{uuid4().hex[:12]}",
                    SCHED_PAYLOAD_SOURCE: "heartbeat",
                    SCHED_PAYLOAD_SESSION_TARGET: "main",
                    SCHED_PAYLOAD_WAKE_MODE: "next_heartbeat",
                },
            )
        )
        self._persist_state(
            now=now,
            status="published",
            reason=decision.reason,
            route={"channel": route.channel, "chat_id": route.chat_id},
            prompt=prompt,
        )
        self.heartbeat_state.record_runner_decision(
            now=now,
            status="published",
            reason=decision.reason,
            route={"channel": route.channel, "chat_id": route.chat_id},
            check_types=decision.check_types,
            due_checks=decision.due_checks,
        )
        logger.info(f"Heartbeat tick published to {route.channel}/{route.chat_id}")

    def _resolve_route(self) -> Optional[LastRoute]:
        if self.target == "main":
            return LastRoute(channel="scheduler", chat_id="main")
        if self.target == "last" and self.route_provider is not None:
            route = self.route_provider()
            if route is None:
                return LastRoute(channel="scheduler", chat_id="main")
            if isinstance(route, LastRoute):
                return route
            if isinstance(route, dict):
                ch = str(route.get("channel") or "")
                cid = str(route.get("chat_id") or "")
                if not ch or not cid:
                    return LastRoute(channel="scheduler", chat_id="main")
                return LastRoute(
                    channel=ch,
                    chat_id=cid,
                    user_id=str(route.get("user_id") or ""),
                    user_name=str(route.get("user_name") or ""),
                )
            return LastRoute(channel="scheduler", chat_id="main")
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

    @staticmethod
    def _parse_state_dt(value: str) -> Optional[datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    def _get_heartbeat_context(self) -> str:
        if self.heartbeat_context_provider is not None:
            try:
                return (self.heartbeat_context_provider() or "").strip()
            except Exception as e:
                logger.warning(f"Heartbeat context provider failed: {e}")
        return self.heartbeat_context

    @staticmethod
    def _has_actionable_heartbeat_context(context: str) -> bool:
        for raw_line in (context or "").splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("<!--"):
                continue
            return True
        return False

    def _build_prompt(self) -> str:
        return self.DEFAULT_PROMPT

    def _persist_state(
        self,
        *,
        now: datetime,
        status: str,
        reason: str,
        route: Optional[dict[str, str]] = None,
        prompt: str = "",
    ) -> None:
        if self.state_path is None:
            return
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "timestamp": now.isoformat(),
                "status": status,
                "reason": reason,
                "target": self.target,
                "interval_minutes": self.interval_minutes,
                "route": route or {},
                "prompt": prompt,
            }
            tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(self.state_path)
        except Exception as e:
            logger.warning(f"Failed to persist heartbeat state: {e}")
