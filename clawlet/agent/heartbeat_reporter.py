"""Heartbeat result recording helper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class HeartbeatReporter:
    heartbeat_state: Any
    now_fn: Callable[[], Any]

    def record_result(
        self,
        *,
        response_text: str,
        channel: str,
        chat_id: str,
        heartbeat_metadata: dict,
        mapped_tool_names: list[str],
        blockers: list[str],
    ) -> None:
        route = {
            "channel": channel,
            "chat_id": chat_id,
        }
        check_types = list(heartbeat_metadata.get("heartbeat_check_types") or [])
        self.heartbeat_state.record_cycle_result(
            now=self.now_fn(),
            response_text=response_text,
            tool_names=list(mapped_tool_names),
            route=route,
            check_types=check_types,
            blockers=list(blockers),
        )
