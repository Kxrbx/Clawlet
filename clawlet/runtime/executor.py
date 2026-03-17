"""Deterministic tool runtime with idempotency and event sourcing."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import re
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
from clawlet.runtime.failures import classify_error_text, to_payload
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
        engine: str = "python",
        remote_executor=None,
        lane_defaults: Optional[dict[str, str]] = None,
    ):
        self.registry = registry
        self.event_store = event_store
        self.policy = policy
        self.enable_idempotency = enable_idempotency
        self.engine = engine
        self.remote_executor = remote_executor
        self._idempotency_cache: dict[str, ToolResult] = {}
        self._lane_locks: dict[str, asyncio.Lock] = {}
        self._lane_defaults = dict(lane_defaults or {})

    async def execute(self, envelope: ToolCallEnvelope, approved: bool = False) -> tuple[ToolResult, ToolExecutionMetadata]:
        """Execute a tool call envelope with policy and replay events."""
        args = envelope.arguments or {}
        lane = self._resolve_lane(envelope)

        self.event_store.append(
            RuntimeEvent(
                event_type=EVENT_TOOL_REQUESTED,
                run_id=envelope.run_id,
                session_id=envelope.session_id,
                payload={
                    "tool_call_id": envelope.tool_call_id,
                    "tool_name": envelope.tool_name,
                    "execution_mode": envelope.execution_mode,
                    "execution_target": envelope.execution_target,
                    "lane": lane,
                    "arguments": args,
                },
            )
        )

        policy_decision = self.policy.authorize(envelope.execution_mode, approved=approved)
        if not policy_decision.allowed:
            result = ToolResult(success=False, output="", error=policy_decision.reason)
            failure = classify_error_text(result.error)
            self.event_store.append(
                RuntimeEvent(
                    event_type=EVENT_TOOL_FAILED,
                    run_id=envelope.run_id,
                    session_id=envelope.session_id,
                    payload={
                        "tool_call_id": envelope.tool_call_id,
                        "tool_name": envelope.tool_name,
                        "lane": lane,
                        "error": result.error,
                        **to_payload(failure),
                    },
                )
            )
            return result, ToolExecutionMetadata(duration_ms=0.0, attempts=0, cached=False)

        idempotency_key = envelope.idempotency_key or self._build_idempotency_key(envelope)
        cacheable = self._is_cacheable(envelope)
        if cacheable and idempotency_key in self._idempotency_cache:
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
                        "lane": lane,
                        "cached": True,
                        "success": cached.success,
                    },
                )
            )
            return cached, meta

        lane_lock = self._lane_lock(lane)
        if lane_lock is None:
            last_result, metadata, use_remote = await self._execute_inner(envelope, args, lane)
        else:
            async with lane_lock:
                last_result, metadata, use_remote = await self._execute_inner(envelope, args, lane)

        if last_result.success:
            if cacheable:
                self._idempotency_cache[idempotency_key] = last_result
            self.event_store.append(
                RuntimeEvent(
                    event_type=EVENT_TOOL_COMPLETED,
                    run_id=envelope.run_id,
                    session_id=envelope.session_id,
                    payload={
                        "tool_call_id": envelope.tool_call_id,
                        "tool_name": envelope.tool_name,
                        "lane": lane,
                        "engine": f"{self.engine}:remote" if use_remote else self.engine,
                        "metadata": asdict(metadata),
                        "success": True,
                        "output": last_result.output,
                    },
                )
            )
        else:
            failure = classify_error_text(last_result.error)
            failure_payload = {
                "tool_call_id": envelope.tool_call_id,
                "tool_name": envelope.tool_name,
                "lane": lane,
                "engine": f"{self.engine}:remote" if use_remote else self.engine,
                "metadata": asdict(metadata),
                "error": last_result.error,
                **to_payload(failure),
            }
            if last_result.output:
                failure_payload["output"] = last_result.output
            if last_result.data is not None:
                failure_payload["data"] = last_result.data
            self.event_store.append(
                RuntimeEvent(
                    event_type=EVENT_TOOL_FAILED,
                    run_id=envelope.run_id,
                    session_id=envelope.session_id,
                    payload=failure_payload,
                )
            )

        return last_result, metadata

    def _is_cacheable(self, envelope: ToolCallEnvelope) -> bool:
        if not self.enable_idempotency:
            return False
        if envelope.cacheable is False:
            return False
        if envelope.execution_mode != "read_only":
            return False

        tool_name = (envelope.tool_name or "").strip().lower()
        if tool_name == "read_file":
            return True
        if tool_name != "fetch_url":
            return False

        url = str((envelope.arguments or {}).get("url", "") or "").strip().lower()
        if not url:
            return False
        if "/api/" in url:
            return False
        if any(marker in url for marker in ("timestamp=", "ts=", "cachebust=", "nocache=", "notifications/")):
            return False
        if re.search(r"/(upvote|downvote|comment|comments|reply|replies|messages|dm|follow|like)\b", url):
            return False
        return True

    def _build_idempotency_key(self, envelope: ToolCallEnvelope) -> str:
        raw = json.dumps(
            {
                "session_id": envelope.session_id,
                "tool_name": envelope.tool_name,
                "arguments": envelope.arguments,
                "execution_mode": envelope.execution_mode,
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
        return classify_error_text(error).retryable

    def _resolve_lane(self, envelope: ToolCallEnvelope) -> str:
        lane = (envelope.lane or "").strip().lower()
        if lane:
            return lane
        configured = self._lane_defaults.get(envelope.execution_mode)
        if isinstance(configured, str) and configured.strip():
            return configured.strip().lower()
        if envelope.execution_mode == "read_only":
            return "parallel:read_only"
        if envelope.execution_mode == "elevated":
            return "serial:elevated"
        return "serial:workspace_write"

    def _lane_lock(self, lane: str) -> Optional[asyncio.Lock]:
        if lane.startswith("parallel:"):
            return None
        lock = self._lane_locks.get(lane)
        if lock is None:
            lock = asyncio.Lock()
            self._lane_locks[lane] = lock
        return lock

    async def _execute_inner(
        self,
        envelope: ToolCallEnvelope,
        args: dict,
        lane: str,
    ) -> tuple[ToolResult, ToolExecutionMetadata, bool]:
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
                    "lane": lane,
                },
            )
        )

        use_remote = envelope.execution_target == "remote" and self.remote_executor is not None
        tool = self.registry.get(envelope.tool_name)
        exec_args = dict(args)
        if tool is not None:
            exec_args.update(self._runtime_context_args(tool, envelope))

        for attempt in range(max(1, envelope.max_retries + 1)):
            attempts += 1
            if use_remote:
                try:
                    result = await self.remote_executor.execute(envelope)
                except Exception as e:
                    result = ToolResult(success=False, output="", error=f"Remote execution exception: {e}")
            else:
                try:
                    result = await asyncio.wait_for(
                        self.registry.execute(envelope.tool_name, **exec_args),
                        timeout=max(0.1, float(envelope.timeout_seconds)),
                    )
                except asyncio.TimeoutError:
                    result = ToolResult(
                        success=False,
                        output="",
                        error=f"Tool execution timed out after {envelope.timeout_seconds:.1f}s",
                    )
            last_result = result
            if result.success or not self._is_retryable_error(result.error):
                break

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        metadata = ToolExecutionMetadata(duration_ms=elapsed_ms, attempts=attempts, cached=False)
        return last_result, metadata, use_remote

    def _runtime_context_args(self, tool, envelope: ToolCallEnvelope) -> dict[str, str]:
        """Inject runtime-only kwargs only when the tool contract can accept them."""
        extra = {"_workspace_path": envelope.workspace_path}
        try:
            from clawlet.plugins.sdk import PluginTool

            if isinstance(tool, PluginTool):
                extra["_run_id"] = envelope.run_id
                extra["_session_id"] = envelope.session_id
        except Exception:
            pass

        try:
            params = inspect.signature(tool.execute).parameters.values()
        except (TypeError, ValueError):
            return {}

        if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params):
            return extra

        accepted = {param.name for param in params}
        return {key: value for key, value in extra.items() if key in accepted}
