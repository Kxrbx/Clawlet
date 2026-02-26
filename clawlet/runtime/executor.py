"""Deterministic tool runtime with idempotency and event sourcing."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from typing import Optional

from clawlet.runtime.events import (
    EVENT_TOOL_COMPLETED,
    EVENT_TOOL_FAILED,
    EVENT_TOOL_REQUESTED,
    EVENT_TOOL_STARTED,
    RuntimeEvent,
    RuntimeEventStore,
)
from clawlet.runtime.policy import RuntimePolicyEngine
from clawlet.runtime.rust_bridge import fast_hash
from clawlet.runtime.types import ToolCallEnvelope, ToolExecutionMetadata
from clawlet.tools.registry import ToolRegistry, ToolResult


class DeterministicToolRuntime:
    """Executes tools through a normalized deterministic contract."""

    def __init__(
        self,
        registry: ToolRegistry,
        event_store: RuntimeEventStore,
        policy: RuntimePolicyEngine,
        enable_idempotency: bool = True,
    ):
        self.registry = registry
        self.event_store = event_store
        self.policy = policy
        self.enable_idempotency = enable_idempotency
        self._idempotency_cache: dict[str, ToolResult] = {}

    async def execute(self, envelope: ToolCallEnvelope, approved: bool = False) -> tuple[ToolResult, ToolExecutionMetadata]:
        """Execute a tool call envelope with policy and replay events."""
        args = envelope.arguments or {}

        self.event_store.append(
            RuntimeEvent(
                event_type=EVENT_TOOL_REQUESTED,
                run_id=envelope.run_id,
                session_id=envelope.session_id,
                payload={
                    "tool_call_id": envelope.tool_call_id,
                    "tool_name": envelope.tool_name,
                    "execution_mode": envelope.execution_mode,
                    "arguments": args,
                },
            )
        )

        policy_decision = self.policy.authorize(envelope.execution_mode, approved=approved)
        if not policy_decision.allowed:
            result = ToolResult(success=False, output="", error=policy_decision.reason)
            self.event_store.append(
                RuntimeEvent(
                    event_type=EVENT_TOOL_FAILED,
                    run_id=envelope.run_id,
                    session_id=envelope.session_id,
                    payload={
                        "tool_call_id": envelope.tool_call_id,
                        "tool_name": envelope.tool_name,
                        "error": result.error,
                    },
                )
            )
            return result, ToolExecutionMetadata(duration_ms=0.0, attempts=0, cached=False)

        idempotency_key = envelope.idempotency_key or self._build_idempotency_key(envelope)
        if self.enable_idempotency and idempotency_key in self._idempotency_cache:
            cached = self._idempotency_cache[idempotency_key]
            meta = ToolExecutionMetadata(duration_ms=0.0, attempts=0, cached=True)
            self.event_store.append(
                RuntimeEvent(
                    event_type=EVENT_TOOL_COMPLETED,
                    run_id=envelope.run_id,
                    session_id=envelope.session_id,
                    payload={
                        "tool_call_id": envelope.tool_call_id,
                        "tool_name": envelope.tool_name,
                        "cached": True,
                        "success": cached.success,
                    },
                )
            )
            return cached, meta

        attempts = 0
        started = time.perf_counter()
        last_result = ToolResult(success=False, output="", error="unknown error")

        self.event_store.append(
            RuntimeEvent(
                event_type=EVENT_TOOL_STARTED,
                run_id=envelope.run_id,
                session_id=envelope.session_id,
                payload={
                    "tool_call_id": envelope.tool_call_id,
                    "tool_name": envelope.tool_name,
                },
            )
        )

        for attempt in range(max(1, envelope.max_retries + 1)):
            attempts += 1
            result = await self.registry.execute(envelope.tool_name, **args)
            last_result = result
            if result.success or not self._is_retryable_error(result.error):
                break

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        metadata = ToolExecutionMetadata(duration_ms=elapsed_ms, attempts=attempts, cached=False)

        if last_result.success:
            if self.enable_idempotency:
                self._idempotency_cache[idempotency_key] = last_result
            self.event_store.append(
                RuntimeEvent(
                    event_type=EVENT_TOOL_COMPLETED,
                    run_id=envelope.run_id,
                    session_id=envelope.session_id,
                    payload={
                        "tool_call_id": envelope.tool_call_id,
                        "tool_name": envelope.tool_name,
                        "metadata": asdict(metadata),
                        "success": True,
                        "output": last_result.output,
                    },
                )
            )
        else:
            self.event_store.append(
                RuntimeEvent(
                    event_type=EVENT_TOOL_FAILED,
                    run_id=envelope.run_id,
                    session_id=envelope.session_id,
                    payload={
                        "tool_call_id": envelope.tool_call_id,
                        "tool_name": envelope.tool_name,
                        "metadata": asdict(metadata),
                        "error": last_result.error,
                    },
                )
            )

        return last_result, metadata

    def _build_idempotency_key(self, envelope: ToolCallEnvelope) -> str:
        raw = json.dumps(
            {
                "session_id": envelope.session_id,
                "tool_name": envelope.tool_name,
                "arguments": envelope.arguments,
                "tool_call_id": envelope.tool_call_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            return fast_hash(raw)
        except Exception:
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_retryable_error(error: Optional[str]) -> bool:
        if not error:
            return False
        normalized = error.lower()
        return any(
            marker in normalized
            for marker in (
                "timeout",
                "temporarily unavailable",
                "rate limit",
                "connection",
                "network",
            )
        )
