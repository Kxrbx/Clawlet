"""Heartbeat-specific turn handling extracted from the generic agent loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class HeartbeatTurnHandler:
    agent: Any

    def maybe_accept_text_only_response(self, response_content: str, tool_calls_used: int) -> str | None:
        final_text = self.agent._sanitize_final_response(response_content, tool_calls_used).strip()
        if (
            final_text == "HEARTBEAT_OK"
            or final_text.startswith("HEARTBEAT_")
            or self.agent._looks_like_blocker_response(final_text)
        ):
            return final_text or response_content
        return None

    def finalize_response(
        self,
        *,
        response_text: str,
        is_error: bool,
        tool_names: list[str],
        blockers: list[str],
        action_summaries: list[str],
    ) -> tuple[str, bool]:
        final_response, final_is_error = self.agent._canonicalize_heartbeat_outcome(
            response_text=response_text,
            is_error=is_error,
            tool_names=tool_names,
            blockers=blockers,
            action_summaries=action_summaries,
            tool_calls_used=len(tool_names),
        )
        self.agent._record_heartbeat_result(
            final_response,
            mapped_tool_names=tool_names,
            blockers=blockers,
        )
        return final_response, final_is_error
