"""Response shaping policy for final text, heartbeat outcomes, and outbound suppression."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from clawlet.tools.registry import ToolResult


@dataclass(slots=True)
class ResponsePolicy:
    continuation_split: re.Pattern[str]
    looks_like_incomplete_followthrough: Callable[[str, int], bool]
    sanitize_template_placeholders: Callable[[str], str]
    looks_like_blocker_response: Callable[[str], bool]

    def strip_tool_call_markup(self, content: str) -> str:
        text = content or ""
        text = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text

    def sanitize_final_response(self, content: str, tool_calls_used: int) -> str:
        cleaned = self.strip_tool_call_markup(content or "")
        if not cleaned:
            return ""

        has_pending_language = bool(self.continuation_split.search(cleaned))
        if has_pending_language or self.looks_like_incomplete_followthrough(cleaned, tool_calls_used):
            head = self.continuation_split.split(cleaned, maxsplit=1)[0].strip()
            if head:
                cleaned = (
                    "Partial progress:\n\n"
                    f"{head}\n\n"
                    "I did not execute the remaining step in this turn."
                )
            else:
                cleaned = "I made partial progress, but I did not execute the remaining step in this turn."

        return self.sanitize_template_placeholders(cleaned)

    def canonicalize_heartbeat_outcome(
        self,
        *,
        response_text: str,
        is_error: bool,
        tool_names: list[str],
        blockers: list[str],
        action_summaries: list[str],
    ) -> tuple[str, bool]:
        text = (response_text or "").strip()
        blocker_text = (blockers[0] if blockers else "").strip()
        if is_error or blocker_text or self.looks_like_blocker_response(text):
            detail = blocker_text or text or "heartbeat run failed"
            detail = detail.splitlines()[0][:220]
            return f"HEARTBEAT_BLOCKED - {detail}", True

        if text == "HEARTBEAT_OK":
            return "HEARTBEAT_OK", False

        meaningful_tools = [
            name for name in tool_names
            if name not in {"read_file", "fetch_url", "list_dir", "get_context", "recall"}
        ]
        if meaningful_tools or action_summaries:
            summary = next((item for item in action_summaries if item), "")
            if not summary:
                summary = text or f"Completed actions using: {', '.join(dict.fromkeys(meaningful_tools))}"
            if not summary.startswith("HEARTBEAT_ACTION_TAKEN"):
                summary = f"HEARTBEAT_ACTION_TAKEN - {summary}"
            return summary, False

        return "HEARTBEAT_OK", False

    @staticmethod
    def summarize_heartbeat_tool_result(tool_name: str, result: ToolResult) -> str:
        if not result.success:
            return ""
        if tool_name in {"read_file", "fetch_url", "list_dir", "get_context", "recall"}:
            return ""
        detail = (result.output or "").strip()
        if detail:
            detail = detail.splitlines()[0].strip()
            if len(detail) > 180:
                detail = detail[:177].rstrip() + "..."
            return detail
        return f"Completed `{tool_name}` successfully."

    @staticmethod
    def should_suppress_outbound(response) -> bool:
        metadata = getattr(response, "metadata", {}) or {}
        if not bool(metadata.get("heartbeat")):
            return False

        text = (getattr(response, "content", "") or "").strip()
        if not text:
            return True
        if getattr(response, "channel", "") == "scheduler":
            return True
        ack_max_chars = int(metadata.get("ack_max_chars", 24) or 24)
        if text.startswith("HEARTBEAT_ACTION_TAKEN"):
            detail = text.partition(" - ")[2].strip()
            if metadata.get("publish_heartbeat_action") is True:
                return False
            if not detail:
                return True
            generic_prefixes = (
                "completed actions using:",
                "completed `",
                "completed ",
                "finished ",
                "done.",
            )
            lowered_detail = detail.lower()
            if lowered_detail.startswith(generic_prefixes):
                return True
            if len(detail) <= ack_max_chars and "\n" not in detail:
                return True
            return False

        if len(text) <= ack_max_chars and "\n" not in text:
            return True
        lowered = text.lower()
        if "temporarily unavailable" in lowered or "repeated failures" in lowered:
            return True
        return False
